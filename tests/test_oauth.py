from urllib.parse import parse_qs, urlparse

from helpers import LI_CREDS, FakeHTTP, FakeResponse, add_linkedin, add_x, services, stored_creds

from aisocial import db


def start(client, account, return_to="settings"):
    resp = client.get(f"/oauth/linkedin/start/{account['id']}?return={return_to}")
    assert resp.status_code == 302
    url = urlparse(resp.headers["Location"])
    return url, parse_qs(url.query)


def test_linkedin_connect_flow(app, client, platforms):
    account = add_linkedin(client)
    url, query = start(client, account, "setup")
    assert (url.netloc, url.path) == ("www.linkedin.com", "/oauth/v2/authorization")
    assert query["client_id"] == [LI_CREDS["client_id"]] and query["response_type"] == ["code"]
    assert query["redirect_uri"] == ["http://localhost:5050/oauth/linkedin/callback"]
    assert query["scope"] == ["openid profile w_member_social"]
    state = query["state"][0]

    platforms["linkedin"].http = FakeHTTP(
        FakeResponse(200, {"access_token": "li-token-123456", "expires_in": 5184000}),
        FakeResponse(200, {"sub": "abc123", "name": "Μαρία Π."}),
    )
    resp = client.get(f"/oauth/linkedin/callback?code=the-code&state={state}")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/setup?linkedin=connected#accounts")
    assert platforms["linkedin"].http.calls[0].data["code"] == "the-code"

    connected = client.get("/api/accounts").get_json()["accounts"][0]
    assert connected["connected"] and connected["ready"] and connected["check"]["username"] == "Μαρία Π."
    assert stored_creds(app, account["id"])["person_urn"] == "urn:li:person:abc123"

    # A state value works only once.
    resp = client.get(f"/oauth/linkedin/callback?code=again&state={state}")
    assert "linkedin_error=" in resp.headers["Location"]


def test_user_cancels_on_linkedin(client):
    account = add_linkedin(client)
    _, query = start(client, account)
    resp = client.get(
        "/oauth/linkedin/callback?error=user_cancelled_authorize"
        f"&error_description=The+user+cancelled&state={query['state'][0]}"
    )
    location = resp.headers["Location"]
    assert location.startswith("/settings?linkedin_error=") and "cancelled" in location


def test_token_exchange_failure_is_reported(client, platforms):
    account = add_linkedin(client)
    _, query = start(client, account)
    platforms["linkedin"].http = FakeHTTP(
        FakeResponse(400, {"error": "invalid_request", "error_description": "redirect_uri mismatch"}),
    )
    resp = client.get(f"/oauth/linkedin/callback?code=c&state={query['state'][0]}")
    assert "linkedin_error=" in resp.headers["Location"]
    assert LI_CREDS["client_secret"] not in resp.headers["Location"]
    assert client.get("/api/accounts").get_json()["accounts"][0]["connected"] is False


def test_start_needs_a_linkedin_account(client):
    x = add_x(client)
    assert "linkedin_error=" in client.get(f"/oauth/linkedin/start/{x['id']}").headers["Location"]
    assert "linkedin_error=" in client.get("/oauth/linkedin/start/999").headers["Location"]


def test_callback_without_valid_state(client):
    assert "linkedin_error=" in client.get("/oauth/linkedin/callback?code=x").headers["Location"]
    assert "linkedin_error=" in client.get("/oauth/linkedin/callback?code=x&state=forged").headers["Location"]


def test_state_expires_after_ten_minutes(app, client):
    account = add_linkedin(client)
    with db.open_db(services(app).settings.db_path) as conn:
        db.save_oauth_state(conn, "old-state", account["id"])
        conn.execute("UPDATE oauth_states SET created_at = created_at - 700 WHERE state = 'old-state'")
    resp = client.get("/oauth/linkedin/callback?code=x&state=old-state")
    assert "linkedin_error=" in resp.headers["Location"]
