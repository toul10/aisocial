"""The home page summary: week view, counts, recent results and publishing history."""

import time

from helpers import add_facebook, add_x, services

from aisocial import db


def stored_post(app, account, *, status, platform="x", scheduled_in=None, published_days_ago=None):
    """A post written straight into the database, e.g. from long ago or left overdue."""
    with db.open_db(services(app).settings.db_path) as conn:
        post_id = db.create_post(
            conn, account_id=account["id"], account_name=account["name"], platform=platform, text="Παλιό",
            image_id=None, status=status, scheduled_at=None if scheduled_in is None else time.time() + scheduled_in,
        )
        if published_days_ago is not None:
            conn.execute("UPDATE posts SET published_at = ? WHERE id = ?", (time.time() - published_days_ago * 86400, post_id))
    return post_id


def schedule(client, account, text, days):
    body = {"posts": [{"account_id": account["id"], "text": text}], "scheduled_at": time.time() + days * 86400}
    return client.post("/api/posts", json=body).get_json()["posts"][0]


def test_dashboard_summary(app, client, platforms):
    x, fb = add_x(client), add_facebook(client)
    client.post("/api/posts", json={"posts": [{"account_id": x["id"], "text": "Τώρα"}]})
    soon = schedule(client, fb, "Σε 2 μέρες", 2)
    schedule(client, x, "Σε 20 μέρες", 20)
    stored_post(app, fb, status="published", platform="facebook", published_days_ago=200)
    overdue = stored_post(app, x, status="scheduled", scheduled_in=-600)  # the app was closed at the time
    failed = stored_post(app, x, status="failed")

    data = client.get("/api/dashboard").get_json()
    assert data["ok"] is True
    assert data["counts"] == {"published": 2, "scheduled": 3, "failed": 1}
    # The week view gets overdue posts too, but nothing beyond the next 8 days.
    assert [p["id"] for p in data["upcoming"]] == [overdue, soon["id"]]
    assert data["upcoming"][1]["platform_label"] == "Facebook Page"
    assert data["next_at"] == soon["scheduled_at"]
    # History covers about three months: the 200-day-old post is left out.
    assert [p["platform"] for p in data["published"]] == ["x"]
    assert failed in [p["id"] for p in data["recent"]]
    assert all(p["status"] in ("published", "failed") for p in data["recent"])


def test_dashboard_when_empty(client):
    data = client.get("/api/dashboard").get_json()
    assert data["counts"] == {} and data["upcoming"] == [] and data["recent"] == [] and data["published"] == []
    assert data["next_at"] is None


def test_scheduled_filter_lists_soonest_first(client, platforms):
    """The posts page shows what goes out next; a long queue must never hide it behind the limit."""
    x = add_x(client)
    later = schedule(client, x, "Σε 3 μέρες", 3)
    sooner = schedule(client, x, "Αύριο", 1)
    posts = client.get("/api/posts?status=scheduled").get_json()["posts"]
    assert [p["id"] for p in posts] == [sooner["id"], later["id"]]
