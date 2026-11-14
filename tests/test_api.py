import pytest
from helpers import (
    ANTHROPIC_KEY, LI_CREDS, OPENAI_KEY, X_CREDS, Client, FakeText, add_account, add_linkedin, add_x,
    connect_linkedin, stored_creds,
)

from aisocial.ai import AIService
from aisocial.crypto import generate_key
from aisocial.platforms import PlatformError


def test_first_visit_goes_to_setup_wizard(client):
    resp = client.get("/")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/setup")
    assert client.post("/api/setup/complete").status_code == 200
    resp = client.get("/")
    assert resp.status_code == 200 and b"js/dashboard.js" in resp.data


@pytest.mark.parametrize("path,script", [
    ("/new", b"js/compose.js"), ("/posts", b"js/posts.js"), ("/settings", b"js/settings.js"), ("/setup", b"js/setup.js"),
])
def test_pages_render(client, path, script):
    resp = client.get(path)
    assert resp.status_code == 200 and script in resp.data
    assert '<html lang="en">' in resp.get_data(as_text=True)  # English unless the user picks Greek


@pytest.mark.parametrize("asset", [
    "js/common.js", "js/dashboard.js", "js/compose.js", "js/panels/accounts.js", "css/style.css", "favicon.svg",
])
def test_static_assets_are_served(client, asset):
    assert client.get(f"/static/{asset}").status_code == 200


def test_state_defaults(client):
    data = client.get("/api/state").get_json()
    assert data["setup_completed"] is False
    assert data["ai"]["text_provider"] is None
    assert [p["key"] for p in data["platforms"]] == ["x", "linkedin", "facebook"]
    assert len(data["topics"]) == 6 and all(t["active"] for t in data["topics"])
    assert data["content"]["brand_voice"]
    linkedin = next(p for p in data["platforms"] if p["key"] == "linkedin")
    assert linkedin["guide"]["copy"] == "http://localhost:5050/oauth/linkedin/callback"
    assert all(p["guide"]["steps"] for p in data["platforms"])


def test_update_content(client):
    resp = client.put("/api/content", json={"brand_name": "  Φούρνος  ", "about": "Προζυμένιο ψωμί"})
    assert resp.get_json()["content"]["brand_name"] == "Φούρνος"
    assert client.get("/api/state").get_json()["content"]["about"] == "Προζυμένιο ψωμί"
    assert client.put("/api/content", json={"about": "x" * 1501}).status_code == 400
    assert client.put("/api/content", json={"about": 5}).status_code == 400


def test_topics(client):
    resp = client.post("/api/topics", json={"title": "  Νέο   θέμα "})
    assert resp.status_code == 201 and resp.get_json()["added"] == 1
    new = next(t for t in resp.get_json()["topics"] if t["title"] == "Νέο θέμα")
    assert client.post("/api/topics", json={"title": "ΝΈΟ ΘΈΜΑ"}).get_json()["added"] == 0
    assert client.post("/api/topics", json={"title": "νέο θέμα"}).get_json()["added"] == 0
    assert client.post("/api/topics", json={"titles": ["Α", "Β", "Α"]}).get_json()["added"] == 2
    resp = client.patch(f"/api/topics/{new['id']}", json={"active": False})
    assert next(t for t in resp.get_json()["topics"] if t["id"] == new["id"])["active"] is False
    assert client.patch(f"/api/topics/{new['id']}", json={"active": "no"}).status_code == 400
    assert client.delete(f"/api/topics/{new['id']}").status_code == 200
    assert client.delete(f"/api/topics/{new['id']}").status_code == 404
    assert client.post("/api/topics", json={"title": "   "}).status_code == 400


def test_account_needs_all_fields(client):
    resp = client.post("/api/accounts", json={"platform": "x", "credentials": {"api_key": "abc"}})
    assert resp.status_code == 400 and "Fill in" in resp.get_json()["error"]
    bad = dict(X_CREDS, api_key="has a space")
    assert client.post("/api/accounts", json={"platform": "x", "credentials": bad}).status_code == 400
    assert client.post("/api/accounts", json={"platform": "myspace", "credentials": {}}).status_code == 400


def test_facebook_page_id_must_be_numeric(client):
    creds = {"page_id": "my-page", "page_access_token": "EAAtoken1234567"}
    assert client.post("/api/accounts", json={"platform": "facebook", "credentials": creds}).status_code == 400


def test_account_lifecycle(app, client, platforms):
    account = add_x(client)
    assert account["ready"] is True and account["name"] == "Brand X"
    assert account["fields"]["api_key"] == {"set": True, "value": None, "hint": "…7890"}

    data = client.post(f"/api/accounts/{account['id']}/verify").get_json()
    assert data["verified"] is True and data["account"]["check"]["username"] == "@tester"

    platforms["x"].error = PlatformError("Το X απέρριψε τα keys (401).", needs_reconnect=True)
    data = client.post(f"/api/accounts/{account['id']}/verify").get_json()
    assert data["verified"] is False and data["account"]["check"]["ok"] is False
    assert "401" in data["account"]["check"]["message"]

    resp = client.put(f"/api/accounts/{account['id']}", json={
        "name": "Renamed", "credentials": {"api_key": "", "access_token": "new-token-123456"},
    })
    updated = resp.get_json()["account"]
    assert updated["name"] == "Renamed" and updated["check"]["ok"] is None
    creds = stored_creds(app, account["id"])
    assert creds["access_token"] == "new-token-123456" and creds["api_key"] == X_CREDS["api_key"]

    assert client.delete(f"/api/accounts/{account['id']}").status_code == 200
    assert client.get("/api/accounts").get_json()["accounts"] == []
    assert client.delete(f"/api/accounts/{account['id']}").status_code == 404


def test_linkedin_account_needs_connect(app, client):
    account = add_linkedin(client)
    assert account["ready"] is False and account["connected"] is False
    assert account["connect_url"] == f"/oauth/linkedin/start/{account['id']}"
    assert account["fields"]["client_id"]["value"] == LI_CREDS["client_id"]
    connect_linkedin(app, account["id"])
    account = client.get("/api/accounts").get_json()["accounts"][0]
    assert account["ready"] is True and account["connected"] is True and account["expires_at"]


def test_linkedin_client_id_change_drops_token(app, client):
    account = add_linkedin(client)
    connect_linkedin(app, account["id"])
    resp = client.put(f"/api/accounts/{account['id']}", json={"credentials": {"client_secret": "rotated-secret-123456"}})
    assert resp.get_json()["account"]["connected"] is True
    resp = client.put(f"/api/accounts/{account['id']}", json={"credentials": {"client_id": "another-app"}})
    assert resp.get_json()["account"]["connected"] is False
    assert "access_token" not in stored_creds(app, account["id"])


def test_expired_linkedin_is_not_ready(app, client):
    account = add_linkedin(client)
    connect_linkedin(app, account["id"], expires_in=-10)
    account = client.get("/api/accounts").get_json()["accounts"][0]
    assert account["ready"] is False and "expired" in account["problem"]


def test_ai_keys(client):
    ai = client.put("/api/ai", json={"anthropic_api_key": ANTHROPIC_KEY}).get_json()["ai"]
    assert ai["text_provider"] == "anthropic" and ai["text_model"] == "claude-opus-5-5"
    assert ai["anthropic"] == {"set": True, "source": "app", "hint": "…" + ANTHROPIC_KEY[-4:]}
    assert ai["image_ready"] is False

    assert client.put("/api/ai", json={"anthropic_api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz"}).status_code == 400
    assert client.put("/api/ai", json={"openai_api_key": ANTHROPIC_KEY}).status_code == 400
    assert client.put("/api/ai", json={"openai_api_key": "too-short"}).status_code == 400
    assert client.put("/api/ai", json={"text_provider": "gemini"}).status_code == 400

    ai = client.put("/api/ai", json={"openai_api_key": OPENAI_KEY, "text_provider": "openai"}).get_json()["ai"]
    assert ai["text_provider"] == "openai" and ai["image_ready"] is True
    # An empty value keeps the saved key.
    assert client.put("/api/ai", json={"openai_api_key": ""}).get_json()["ai"]["openai"]["set"] is True
    ai = client.put("/api/ai", json={"openai_api_key": None}).get_json()["ai"]
    assert ai["text_provider"] is None and ai["openai"]["set"] is False  # still prefers OpenAI
    ai = client.put("/api/ai", json={"text_provider": "auto"}).get_json()["ai"]
    assert ai["text_provider"] == "anthropic"


def test_env_key_overrides_and_locks(new_app):
    client = Client(new_app(ANTHROPIC_API_KEY=ANTHROPIC_KEY, AI_TEXT_PROVIDER="anthropic"))
    ai = client.get("/api/ai").get_json()["ai"]
    assert ai["anthropic"]["source"] == "env" and ai["preference_locked"] is True
    assert ai["text_provider"] == "anthropic"


def test_ai_check(client, monkeypatch):
    monkeypatch.setattr(AIService, "_make_text", lambda self, provider, key: FakeText())
    client.put("/api/ai", json={"anthropic_api_key": ANTHROPIC_KEY})
    results = client.post("/api/ai/check").get_json()["results"]
    assert results["anthropic"] == {"ok": True, "message": "Fake OK"}
    assert results["openai"]["ok"] is None


def test_changed_app_secret_is_reported_not_a_crash(app, client, new_app):
    account = add_x(client)
    client.put("/api/ai", json={"anthropic_api_key": ANTHROPIC_KEY})
    other = Client(new_app(APP_SECRET=generate_key()))
    state = other.get("/api/state").get_json()
    assert state["accounts"][0]["ready"] is False
    assert "APP_SECRET" in state["accounts"][0]["problem"]
    assert state["ai"]["anthropic"]["set"] is False
    # Typing the keys again repairs the account.
    resp = other.put(f"/api/accounts/{account['id']}", json={"credentials": X_CREDS})
    assert resp.get_json()["account"]["ready"] is True


def test_invalid_json_body_is_a_clean_error(client):
    resp = client.http.post("/api/topics", data="not json", headers={"X-AISocial-Request": "1", "Content-Type": "application/json"},
                            base_url="http://localhost:5050")
    assert resp.status_code == 400 and resp.get_json()["ok"] is False


def test_account_names_default_to_platform_label(client):
    account = add_account(client, "x", X_CREDS)
    assert account["name"] == "X (Twitter)"
