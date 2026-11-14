"""Test doubles and helpers. Nothing here talks to the network."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

from requests.structures import CaseInsensitiveDict

from aisocial import db
from aisocial.crypto import generate_key
from aisocial.platforms import FacebookPlatform, PublishResult, XPlatform

BASE = "http://localhost:5050"
SECRET = generate_key()
ANTHROPIC_KEY = "sk-ant-api03-test-key-0123456789abcdef"
OPENAI_KEY = "sk-proj-test-key-0123456789abcdefghij"
X_CREDS = {
    "api_key": "xkey-1234567890",
    "api_secret": "xsecret-1234567890",
    "access_token": "xtoken-1234567890",
    "access_token_secret": "xtsecret-1234567890",
}
FB_CREDS = {"page_id": "104857392018273", "page_access_token": "EAAfaketoken1234567890"}
LI_CREDS = {"client_id": "77abcdefgh", "client_secret": "li-secret-1234567890"}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None, text=None, content=b""):
        self.status_code = status_code
        self._json = json_data
        self.headers = CaseInsensitiveDict(headers or {})
        self.text = text if text is not None else (json.dumps(json_data) if json_data is not None else "")
        self.content = content

    def json(self):
        if self._json is None:
            raise ValueError("no JSON body")
        return self._json


class FakeHTTP:
    """Stands in for the requests module: returns queued responses and records calls."""

    def __init__(self, *responses):
        self.queue = list(responses)
        self.calls = []

    def _next(self, method, url, **kwargs):
        self.calls.append(SimpleNamespace(method=method, url=url, **kwargs))
        if not self.queue:
            raise AssertionError(f"unexpected HTTP call: {method} {url}")
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, url, **kwargs):
        return self._next("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._next("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self._next("PUT", url, **kwargs)

    def request(self, method, url, **kwargs):
        return self._next(method, url, **kwargs)


class _Recording:
    def _setup(self):
        self.published = []
        self.error = None
        self.username = "@tester"

    def verify(self, creds):
        if self.error:
            raise self.error
        return {"username": self.username}

    def publish(self, creds, text, image=None):
        if self.error:
            raise self.error
        self.published.append({"creds": creds, "text": text, "image": image})
        n = len(self.published)
        return PublishResult(str(n), f"{self.url_base}{n}")


class FakeX(_Recording, XPlatform):
    url_base = "https://x.com/i/web/status/"

    def __init__(self):
        XPlatform.__init__(self, http=FakeHTTP())
        self._setup()


class FakeFacebook(_Recording, FacebookPlatform):
    url_base = "https://www.facebook.com/"

    def __init__(self):
        FacebookPlatform.__init__(self, "v26.0", http=FakeHTTP())
        self._setup()


class FakeText:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, prompt):
        self.calls.append((system, prompt))
        return self.replies.pop(0) if self.replies else "Ένα δοκιμαστικό post."

    def verify(self):
        return "Fake OK"


class FakeImages:
    def __init__(self, data=JPEG):
        self.data = data
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.data

    def verify(self):
        return "Fake images OK"


class Recorder:
    """A callable that records its keyword arguments, for fake SDK clients."""

    def __init__(self, result):
        self.result = result
        self.args = None
        self.kwargs = None

    def __call__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class Client:
    """Flask test client that sends the CSRF header and the right Host."""

    def __init__(self, app):
        self.app = app
        self.http = app.test_client()

    def _call(self, method, path, json=None, headers=None, **kwargs):
        all_headers = {"X-AISocial-Request": "1", **(headers or {})}
        return self.http.open(path, method=method, json=json, headers=all_headers, base_url=BASE, **kwargs)

    def get(self, path, **kwargs):
        return self._call("GET", path, **kwargs)

    def post(self, path, json=None, **kwargs):
        return self._call("POST", path, json=json, **kwargs)

    def put(self, path, json=None, **kwargs):
        return self._call("PUT", path, json=json, **kwargs)

    def patch(self, path, json=None, **kwargs):
        return self._call("PATCH", path, json=json, **kwargs)

    def delete(self, path, **kwargs):
        return self._call("DELETE", path, **kwargs)


def services(app):
    return app.extensions["aisocial"]


def add_account(client, platform, creds, name=None):
    body = {"platform": platform, "credentials": creds}
    if name:
        body["name"] = name
    resp = client.post("/api/accounts", json=body)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["account"]


def add_x(client, name="Brand X"):
    return add_account(client, "x", X_CREDS, name)


def add_facebook(client, name="Brand Page"):
    return add_account(client, "facebook", FB_CREDS, name)


def add_linkedin(client, name="Me on LinkedIn"):
    return add_account(client, "linkedin", LI_CREDS, name)


def stored_creds(app, account_id):
    s = services(app)
    with db.open_db(s.settings.db_path) as conn:
        return s.box.decrypt_json(db.get_account(conn, account_id)["credentials_enc"])


def connect_linkedin(app, account_id, expires_in=60 * 86400):
    """Pretend the OAuth flow finished."""
    s = services(app)
    creds = dict(LI_CREDS, access_token="li-access-123456", expires_at=time.time() + expires_in,
                 person_urn="urn:li:person:abc123", member_name="Μαρία Π.")
    with db.open_db(s.settings.db_path) as conn:
        db.update_account(conn, account_id, credentials_enc=s.box.encrypt_json(creds))
    return creds
