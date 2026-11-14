"""Platform clients against recorded request/response shapes (no network)."""

import time
from datetime import date

import pytest
import requests
from helpers import FB_CREDS, JPEG, LI_CREDS, PNG, X_CREDS, FakeHTTP, FakeResponse

from aisocial.platforms import FacebookPlatform, Image, LinkedInPlatform, PlatformError, XPlatform
from aisocial.platforms.base import error_detail, redact
from aisocial.platforms.linkedin import recent_versions, to_little_text
from aisocial.platforms.x import weighted_length

LI_CONNECTED = dict(LI_CREDS, access_token="li-access-123456", expires_at=time.time() + 86400,
                    person_urn="urn:li:person:abc123")


# --- X ---------------------------------------------------------------------------

def test_x_weighted_length():
    assert weighted_length("Καλημέρα") == 8
    assert weighted_length("hi 👋") == 5
    assert weighted_length("中文") == 4
    assert weighted_length("δες https://example.com/a/very/long/path?x=1") == 4 + 23


def test_x_publish_text():
    http = FakeHTTP(FakeResponse(201, {"data": {"id": "123", "text": "Γεια"}}))
    result = XPlatform(http=http).publish(X_CREDS, "Γεια")
    call = http.calls[0]
    assert (call.method, call.url, call.json) == ("POST", "https://api.x.com/2/tweets", {"text": "Γεια"})
    assert call.auth is not None
    assert (result.external_id, result.url) == ("123", "https://x.com/i/web/status/123")


def test_x_image_is_uploaded_first():
    http = FakeHTTP(FakeResponse(200, {"data": {"id": "999", "media_key": "3_999"}}), FakeResponse(201, {"data": {"id": "5"}}))
    XPlatform(http=http).publish(X_CREDS, "Με εικόνα", Image(PNG, "image/png", "image.png"))
    upload, tweet = http.calls
    assert upload.url == "https://api.x.com/2/media/upload"
    assert upload.data == {"media_category": "tweet_image", "media_type": "image/png"}
    assert upload.files["media"] == ("image.png", PNG, "image/png")
    assert tweet.json == {"text": "Με εικόνα", "media": {"media_ids": ["999"]}}


def test_x_errors():
    http = FakeHTTP(FakeResponse(401, {"title": "Unauthorized", "detail": "Unauthorized"}))
    with pytest.raises(PlatformError) as err:
        XPlatform(http=http).publish(X_CREDS, "a")
    assert err.value.needs_reconnect and "401" in str(err.value)

    http = FakeHTTP(FakeResponse(403, {"detail": "You are not permitted to perform this action."}))
    with pytest.raises(PlatformError) as err:
        XPlatform(http=http).publish(X_CREDS, "a")
    assert "Read and write" in str(err.value) and not err.value.needs_reconnect

    http = FakeHTTP(requests.ConnectionError("network down"))
    with pytest.raises(PlatformError) as err:
        XPlatform(http=http).publish(X_CREDS, "a")
    assert err.value.maybe_published


def test_x_verify():
    http = FakeHTTP(FakeResponse(200, {"data": {"id": "1", "name": "Brand", "username": "brand"}}))
    assert XPlatform(http=http).verify(X_CREDS) == {"username": "@brand", "display_name": "Brand"}
    assert http.calls[0].url == "https://api.x.com/2/users/me"


# --- LinkedIn ------------------------------------------------------------------------

def test_little_text_escaping_keeps_hashtags():
    assert to_little_text("Νέο (δωρεάν) προϊόν! #Φούρνος @φίλος") == r"Νέο \(δωρεάν\) προϊόν! #Φούρνος \@φίλος"
    assert to_little_text("a_b*c [x]") == r"a\_b\*c \[x\]"
    assert to_little_text("C# rocks") == r"C\# rocks"


def test_recent_versions():
    assert recent_versions(date(2026, 1, 15), count=3) == ["202512", "202511", "202510"]


def test_linkedin_publish():
    http = FakeHTTP(FakeResponse(201, headers={"x-restli-id": "urn:li:share:777"}))
    result = LinkedInPlatform(http=http).publish(LI_CONNECTED, "Γεια (σε όλους)")
    call = http.calls[0]
    assert (call.method, call.url) == ("POST", "https://api.linkedin.com/rest/posts")
    assert call.headers["LinkedIn-Version"] == recent_versions()[0]
    assert call.headers["X-Restli-Protocol-Version"] == "2.0.0"
    assert call.headers["Authorization"] == "Bearer li-access-123456"
    assert call.json["author"] == "urn:li:person:abc123"
    assert call.json["commentary"] == r"Γεια \(σε όλους\)"
    assert call.json["visibility"] == "PUBLIC" and call.json["lifecycleState"] == "PUBLISHED"
    assert result.external_id == "urn:li:share:777"
    assert result.url == "https://www.linkedin.com/feed/update/urn:li:share:777/"


def test_linkedin_falls_back_to_an_older_version_and_remembers_it():
    http = FakeHTTP(
        FakeResponse(426, {"message": "Requested version is not active"}),
        FakeResponse(201, headers={"x-restli-id": "urn:li:share:1"}),
        FakeResponse(201, headers={"x-restli-id": "urn:li:share:2"}),
    )
    platform = LinkedInPlatform(http=http)
    platform.publish(LI_CONNECTED, "a")
    platform.publish(LI_CONNECTED, "b")
    versions = recent_versions()
    assert [c.headers["LinkedIn-Version"] for c in http.calls] == [versions[0], versions[1], versions[1]]


def test_linkedin_pinned_version():
    http = FakeHTTP(FakeResponse(201, headers={"x-restli-id": "urn:li:share:1"}))
    LinkedInPlatform("202605", http=http).publish(LI_CONNECTED, "a")
    assert http.calls[0].headers["LinkedIn-Version"] == "202605"


def test_linkedin_image_upload():
    http = FakeHTTP(
        FakeResponse(200, {"value": {"uploadUrl": "https://www.linkedin.com/dms-uploads/abc", "image": "urn:li:image:42"}}),
        FakeResponse(201),
        FakeResponse(201, headers={"x-restli-id": "urn:li:share:9"}),
    )
    LinkedInPlatform(http=http).publish(LI_CONNECTED, "Με εικόνα", Image(JPEG, "image/jpeg", "image.jpg"))
    init, put, post = http.calls
    assert init.url.endswith("/rest/images?action=initializeUpload")
    assert init.json == {"initializeUploadRequest": {"owner": "urn:li:person:abc123"}}
    assert put.method == "PUT" and put.data == JPEG and put.headers["Authorization"] == "Bearer li-access-123456"
    assert post.json["content"] == {"media": {"id": "urn:li:image:42"}}


def test_linkedin_token_is_not_sent_to_other_upload_hosts():
    http = FakeHTTP(
        FakeResponse(200, {"value": {"uploadUrl": "https://uploads.example-cdn.com/abc", "image": "urn:li:image:1"}}),
        FakeResponse(201),
        FakeResponse(201, headers={"x-restli-id": "urn:li:share:1"}),
    )
    LinkedInPlatform(http=http).publish(LI_CONNECTED, "a", Image(PNG, "image/png", "image.png"))
    assert "Authorization" not in http.calls[1].headers


def test_linkedin_needs_a_valid_token():
    with pytest.raises(PlatformError) as err:
        LinkedInPlatform(http=FakeHTTP()).publish(dict(LI_CONNECTED, expires_at=time.time() - 5), "a")
    assert err.value.needs_reconnect
    with pytest.raises(PlatformError) as err:
        LinkedInPlatform(http=FakeHTTP()).publish(LI_CREDS, "a")
    assert err.value.needs_reconnect


def test_linkedin_exchange_code():
    http = FakeHTTP(
        FakeResponse(200, {"access_token": "tok-123456789", "expires_in": 5184000}),
        FakeResponse(200, {"sub": "xyz", "name": "Μαρία"}),
    )
    creds = LinkedInPlatform(http=http).exchange_code(LI_CREDS, "code-1", "http://localhost:5050/oauth/linkedin/callback")
    assert creds["access_token"] == "tok-123456789" and creds["person_urn"] == "urn:li:person:xyz"
    assert creds["member_name"] == "Μαρία" and creds["expires_at"] > time.time() + 59 * 86400
    token_call, userinfo_call = http.calls
    assert token_call.data["grant_type"] == "authorization_code"
    assert token_call.data["redirect_uri"] == "http://localhost:5050/oauth/linkedin/callback"
    assert userinfo_call.headers["Authorization"] == "Bearer tok-123456789"


def test_linkedin_duplicate_content():
    http = FakeHTTP(FakeResponse(422, {"message": "Content is a duplicate of urn:li:share:1"}))
    with pytest.raises(PlatformError) as err:
        LinkedInPlatform(http=http).publish(LI_CONNECTED, "a")
    assert "422" in str(err.value) and "duplicate" in str(err.value)


# --- Facebook ----------------------------------------------------------------------

def test_facebook_feed_post_keeps_token_out_of_the_url():
    http = FakeHTTP(FakeResponse(200, {"id": "104857392018273_555"}))
    result = FacebookPlatform(http=http).publish(FB_CREDS, "Καλημέρα")
    call = http.calls[0]
    assert call.url == "https://graph.facebook.com/v26.0/104857392018273/feed"
    assert call.data == {"message": "Καλημέρα"}
    assert call.headers == {"Authorization": f"Bearer {FB_CREDS['page_access_token']}"}
    assert FB_CREDS["page_access_token"] not in call.url
    assert result.url == "https://www.facebook.com/104857392018273_555"


def test_facebook_photo_post():
    http = FakeHTTP(FakeResponse(200, {"id": "photo1", "post_id": "104857392018273_777"}))
    result = FacebookPlatform(http=http).publish(FB_CREDS, "Με φωτό", Image(PNG, "image/png", "image.png"))
    call = http.calls[0]
    assert call.url.endswith("/104857392018273/photos")
    assert call.files["source"] == ("image.png", PNG, "image/png") and call.data["message"] == "Με φωτό"
    assert result.external_id == "104857392018273_777"


def test_facebook_expired_token_needs_reconnect():
    http = FakeHTTP(FakeResponse(400, {"error": {"message": "Error validating access token", "type": "OAuthException", "code": 190}}))
    with pytest.raises(PlatformError) as err:
        FacebookPlatform(http=http).publish(FB_CREDS, "a")
    assert err.value.needs_reconnect and "Error validating access token" in str(err.value)


def test_facebook_verify():
    http = FakeHTTP(FakeResponse(200, {"id": "104857392018273", "name": "Φούρνος"}))
    assert FacebookPlatform(http=http).verify(FB_CREDS)["username"] == "Φούρνος"
    assert http.calls[0].params == {"fields": "id,name"}


# --- shared --------------------------------------------------------------------------

def test_error_detail_shapes():
    assert error_detail(FakeResponse(400, {"error": {"message": "fb message"}})) == "fb message"
    assert error_detail(FakeResponse(400, {"error": "invalid_grant", "error_description": "expired"})) == "invalid_grant: expired"
    assert error_detail(FakeResponse(403, {"detail": "x detail"})) == "x detail"
    assert error_detail(FakeResponse(400, {"errors": [{"message": "first"}]})) == "first"
    assert error_detail(FakeResponse(502, text="Bad gateway")) == "Bad gateway"


def test_redact():
    assert redact("token abc123456 leaked", ["abc123456", "short", 42]) == "token *** leaked"
