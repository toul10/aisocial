import base64

import pytest
from helpers import ANTHROPIC_KEY, BASE, SECRET, X_CREDS, Client, add_x, services

from aisocial.config import ConfigError, Settings


def test_unknown_host_is_rejected(client):
    # Blocks DNS rebinding: a hostile page cannot talk to the app under its own name.
    assert client.http.get("/api/state", base_url="http://attacker.example:5050").status_code == 400
    assert client.http.get("/", base_url="http://localhost:9999").status_code == 400


def test_loopback_hosts_are_allowed(client):
    for base in ("http://localhost:5050", "http://127.0.0.1:5050", "http://[::1]:5050"):
        assert client.http.get("/healthz", base_url=base).status_code == 200


def test_post_without_csrf_header_is_rejected(client):
    assert client.http.post("/api/setup/complete", base_url=BASE).status_code == 403


def test_post_from_another_origin_is_rejected(client):
    resp = client.post("/api/setup/complete", headers={"Origin": "http://evil.example"})
    assert resp.status_code == 403


def test_post_from_own_origin_is_allowed(client):
    assert client.post("/api/setup/complete", headers={"Origin": BASE}).status_code == 200


def test_security_headers(client):
    resp = client.get("/setup")
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
    assert "script-src 'self'" in resp.headers["Content-Security-Policy"]
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert client.get("/api/state").headers["Cache-Control"] == "no-store"


def test_password_protects_everything_except_healthz(new_app):
    http = new_app(AISOCIAL_PASSWORD="hunter22").test_client()
    good = {"Authorization": "Basic " + base64.b64encode(b"me:hunter22").decode()}
    bad = {"Authorization": "Basic " + base64.b64encode(b"me:wrong").decode()}
    assert http.get("/setup", base_url=BASE).status_code == 401
    assert http.get("/setup", base_url=BASE, headers=bad).status_code == 401
    assert http.get("/setup", base_url=BASE, headers=good).status_code == 200
    assert http.get("/healthz", base_url=BASE).status_code == 200


def test_config_needs_a_valid_app_secret():
    with pytest.raises(ConfigError):
        Settings.from_env({})
    with pytest.raises(ConfigError):
        Settings.from_env({"APP_SECRET": "not-a-fernet-key"})


def test_config_refuses_network_host_without_password():
    with pytest.raises(ConfigError):
        Settings.from_env({"APP_SECRET": SECRET, "AISOCIAL_HOST": "0.0.0.0"})
    s = Settings.from_env({"APP_SECRET": SECRET, "AISOCIAL_HOST": "0.0.0.0", "AISOCIAL_PASSWORD": "pw"})
    assert s.host == "0.0.0.0"


def test_public_url_sets_allowed_host_and_redirect_uri():
    s = Settings.from_env({
        "APP_SECRET": SECRET, "AISOCIAL_PUBLIC_URL": "https://social.example.com/",
        "AISOCIAL_HOST": "0.0.0.0", "AISOCIAL_PASSWORD": "pw",
    })
    assert "social.example.com" in s.allowed_hosts
    assert s.linkedin_redirect_uri == "https://social.example.com/oauth/linkedin/callback"


def test_api_never_returns_secret_values(client):
    add_x(client)
    client.put("/api/ai", json={"anthropic_api_key": ANTHROPIC_KEY})
    for path in ("/api/state", "/api/accounts", "/api/ai"):
        body = client.get(path).get_data(as_text=True)
        for secret in (*X_CREDS.values(), ANTHROPIC_KEY):
            assert secret not in body, (path, secret)


def test_secrets_are_encrypted_on_disk(app, client):
    add_x(client)
    client.put("/api/ai", json={"anthropic_api_key": ANTHROPIC_KEY})
    db_path = services(app).settings.db_path
    raw = b"".join(p.read_bytes() for p in db_path.parent.glob(db_path.name + "*"))
    for secret in (*X_CREDS.values(), ANTHROPIC_KEY):
        assert secret.encode() not in raw


def test_unknown_api_path_returns_json(client):
    resp = client.get("/api/nothing-here")
    assert resp.status_code == 404
    assert resp.get_json()["ok"] is False


def test_client_helper_matches_real_browser_headers(app):
    # Sanity check for the helper used by the other tests.
    assert Client(app).post("/api/setup/complete").status_code == 200
