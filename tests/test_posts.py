import io
import time

from helpers import PNG, X_CREDS, add_facebook, add_linkedin, add_x, connect_linkedin, services

from aisocial import db
from aisocial.platforms import PlatformError


def post_one(client, account, text="Γεια σου κόσμε", **extra):
    return client.post("/api/posts", json={"posts": [{"account_id": account["id"], "text": text}], **extra})


def test_publish_now(client, platforms):
    account = add_x(client)
    resp = post_one(client, account)
    assert resp.status_code == 201
    post = resp.get_json()["posts"][0]
    assert post["status"] == "published" and post["external_url"] == "https://x.com/i/web/status/1"
    assert post["published_at"] and post["platform_label"] == "X (Twitter)"
    assert platforms["x"].published == [{"creds": X_CREDS, "text": "Γεια σου κόσμε", "image": None}]


def test_publish_to_several_accounts_with_an_image(client, platforms):
    x, fb = add_x(client), add_facebook(client)
    upload = client.post("/api/images", data={"file": (io.BytesIO(PNG), "photo.png")}, content_type="multipart/form-data")
    image = upload.get_json()["image"]
    resp = client.post("/api/posts", json={
        "image_id": image["id"],
        "posts": [{"account_id": x["id"], "text": "Για το X"}, {"account_id": fb["id"], "text": "Για το Facebook"}],
    })
    posts = resp.get_json()["posts"]
    assert [p["status"] for p in posts] == ["published", "published"]
    assert posts[0]["image_url"] == image["url"]
    assert platforms["x"].published[0]["image"].mime == "image/png"
    assert platforms["x"].published[0]["image"].data == PNG
    assert platforms["facebook"].published[0]["text"] == "Για το Facebook"


def test_failure_is_recorded_and_secrets_are_redacted(client, platforms):
    account = add_x(client)
    platforms["x"].error = PlatformError(f"Σφάλμα με token {X_CREDS['access_token']}", needs_reconnect=True)
    post = post_one(client, account).get_json()["posts"][0]
    assert post["status"] == "failed"
    assert X_CREDS["access_token"] not in post["error"] and "***" in post["error"]
    assert client.get("/api/accounts").get_json()["accounts"][0]["check"]["ok"] is False

    platforms["x"].error = None
    retried = client.post(f"/api/posts/{post['id']}/publish").get_json()["post"]
    assert retried["status"] == "published" and retried["error"] is None
    assert client.post(f"/api/posts/{post['id']}/publish").status_code == 409


def test_unexpected_exception_never_leaves_post_stuck(client, platforms):
    account = add_x(client)
    platforms["x"].error = RuntimeError("kaboom")
    post = post_one(client, account).get_json()["posts"][0]
    assert post["status"] == "failed" and "kaboom" in post["error"]


def test_scheduled_post_is_published_once_when_due(app, client, platforms):
    account = add_x(client)
    when = time.time() + 3600
    post = post_one(client, account, scheduled_at=when).get_json()["posts"][0]
    assert post["status"] == "scheduled" and post["scheduled_at"] == when
    assert platforms["x"].published == []
    scheduler = services(app).scheduler
    assert scheduler.tick(at=when - 10) == 0
    assert scheduler.tick(at=when + 5) == 1
    assert scheduler.tick(at=when + 20) == 0
    assert len(platforms["x"].published) == 1
    published = client.get("/api/posts?status=published").get_json()["posts"]
    assert [p["id"] for p in published] == [post["id"]]


def test_post_missed_while_app_was_off_is_not_published_late(app, client, platforms):
    account = add_x(client)
    when = time.time() + 3600
    post = post_one(client, account, scheduled_at=when).get_json()["posts"][0]
    assert services(app).scheduler.tick(at=when + 7 * 3600) == 1
    failed = client.get("/api/posts?status=failed").get_json()["posts"][0]
    assert failed["id"] == post["id"] and "was not running" in failed["error"]
    assert platforms["x"].published == []


def test_validation_happens_before_anything_is_saved(client, platforms):
    account = add_x(client)
    now = time.time()
    cases = [
        {"posts": []},
        {"posts": [{"account_id": account["id"], "text": "a"}], "scheduled_at": now - 60},
        {"posts": [{"account_id": account["id"], "text": "a"}], "scheduled_at": now + 400 * 86400},
        {"posts": [{"account_id": account["id"], "text": "a"}], "scheduled_at": "tomorrow"},
        {"posts": [{"account_id": account["id"], "text": "a"}, {"account_id": account["id"], "text": "b"}]},
        {"posts": [{"account_id": account["id"], "text": "α" * 281}]},
        {"posts": [{"account_id": account["id"], "text": "   "}]},
        {"posts": [{"account_id": account["id"], "text": "a"}], "image_id": "0" * 32 + ".png"},
        {"posts": [{"account_id": "x", "text": "a"}]},
    ]
    for body in cases:
        resp = client.post("/api/posts", json=body)
        assert resp.status_code == 400, (body, resp.get_json())
    assert client.post("/api/posts", json={"posts": [{"account_id": 999, "text": "a"}]}).status_code == 404
    assert client.get("/api/posts").get_json()["posts"] == []
    assert platforms["x"].published == []


def test_x_counts_urls_as_23_characters(client):
    account = add_x(client)
    text = "Δες εδώ: https://example.com/" + "a" * 300
    assert post_one(client, account, text=text).status_code == 201


def test_linkedin_must_be_connected_and_valid_at_publish_time(app, client):
    account = add_linkedin(client)
    resp = post_one(client, account)
    assert resp.status_code == 400 and "Not connected" in resp.get_json()["error"]
    connect_linkedin(app, account["id"], expires_in=2 * 86400)
    resp = post_one(client, account, scheduled_at=time.time() + 3 * 86400)
    assert resp.status_code == 400 and "expires" in resp.get_json()["error"]
    assert post_one(client, account, scheduled_at=time.time() + 86400).status_code == 201


def test_cancel_edit_and_delete(client):
    account = add_x(client)
    post = post_one(client, account, scheduled_at=time.time() + 3600).get_json()["posts"][0]

    later = time.time() + 7200
    edited = client.patch(f"/api/posts/{post['id']}", json={"text": "Νέο κείμενο", "scheduled_at": later}).get_json()["post"]
    assert edited["text"] == "Νέο κείμενο" and edited["scheduled_at"] == later
    assert client.patch(f"/api/posts/{post['id']}", json={"text": "α" * 300}).status_code == 400
    assert client.patch(f"/api/posts/{post['id']}", json={"scheduled_at": None}).status_code == 400

    assert client.delete(f"/api/posts/{post['id']}").status_code == 409  # cancel first
    assert client.post(f"/api/posts/{post['id']}/cancel").get_json()["post"]["status"] == "cancelled"
    assert client.post(f"/api/posts/{post['id']}/cancel").status_code == 409
    assert client.patch(f"/api/posts/{post['id']}", json={"text": "x"}).status_code == 409
    assert client.delete(f"/api/posts/{post['id']}").status_code == 200
    assert client.delete(f"/api/posts/{post['id']}").status_code == 404


def test_cancelled_post_can_be_published_now(client, platforms):
    account = add_x(client)
    post = post_one(client, account, scheduled_at=time.time() + 3600).get_json()["posts"][0]
    client.post(f"/api/posts/{post['id']}/cancel")
    assert client.post(f"/api/posts/{post['id']}/publish").get_json()["post"]["status"] == "published"
    assert len(platforms["x"].published) == 1


def test_deleting_an_account_cancels_its_scheduled_posts(client):
    account = add_x(client)
    post = post_one(client, account, scheduled_at=time.time() + 3600).get_json()["posts"][0]
    assert client.delete(f"/api/accounts/{account['id']}").get_json()["cancelled"] == 1
    cancelled = client.get("/api/posts").get_json()["posts"][0]
    assert cancelled["id"] == post["id"] and cancelled["status"] == "cancelled"
    assert client.post(f"/api/posts/{post['id']}/publish").status_code == 409


def test_post_list_counts_and_filter(client):
    account = add_x(client)
    post_one(client, account)
    post_one(client, account, text="Αργότερα", scheduled_at=time.time() + 3600)
    data = client.get("/api/posts").get_json()
    assert data["counts"] == {"published": 1, "scheduled": 1}
    assert data["posts"][0]["status"] == "scheduled"  # scheduled first
    assert client.get("/api/posts?status=bogus").status_code == 400


def test_interrupted_publish_is_marked_failed_on_restart(app, client, new_app):
    account = add_x(client)
    with db.open_db(services(app).settings.db_path) as conn:
        post_id = db.create_post(conn, account_id=account["id"], account_name="Brand X", platform="x",
                                 text="Μισό", image_id=None, status="publishing", scheduled_at=None)
    new_app()
    with db.open_db(services(app).settings.db_path) as conn:
        post = db.get_post(conn, post_id)
    assert post["status"] == "failed" and "may have gone out" in post["error"]


def test_claim_prevents_double_publishing(app, client, platforms):
    account = add_x(client)
    post = post_one(client, account, scheduled_at=time.time() + 3600).get_json()["posts"][0]
    publisher = services(app).publisher
    with db.open_db(services(app).settings.db_path) as conn:
        first = publisher.publish(conn, post["id"])
        second = publisher.publish(conn, post["id"])
    assert first["status"] == second["status"] == "published"
    assert len(platforms["x"].published) == 1
