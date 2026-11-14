"""Interface language: English by default, Greek on request, for pages, API messages and starter content."""

import time

import pytest
from helpers import Client, add_x, services

from aisocial import db, i18n


def set_language(client, language):
    return client.put("/api/ui", json={"language": language})


def topic_titles(client):
    return [t["title"] for t in client.get("/api/state").get_json()["topics"]]


def test_english_is_the_default(client):
    state = client.get("/api/state").get_json()
    assert state["language"] == "en"
    assert b'<html lang="en"' in client.get("/settings").data
    assert client.get("/api/posts?status=bogus").get_json()["error"] == "Invalid filter."
    assert topic_titles(client)[0] == db.STARTER_TOPICS["en"][0]
    assert state["content"]["brand_voice"] == db.STARTER_VOICE["en"]


def test_switching_to_greek_changes_pages_messages_and_guides(client):
    assert set_language(client, "el").get_json() == {"ok": True, "language": "el"}
    state = client.get("/api/state").get_json()
    assert state["language"] == "el"
    assert b'<html lang="el"' in client.get("/settings").data
    assert client.get("/api/posts?status=bogus").get_json()["error"] == "Μη έγκυρο φίλτρο."
    assert state["ai_guides"]["anthropic"]["title"].startswith("Claude (Anthropic), προτείνεται")
    assert set_language(client, "en").status_code == 200
    assert client.get("/api/posts?status=bogus").get_json()["error"] == "Invalid filter."


@pytest.mark.parametrize("value", ["fr", "", None, 1, ["el"]])
def test_unknown_language_is_refused(client, value):
    resp = client.put("/api/ui", json={"language": value})
    assert resp.status_code == 400
    assert client.get("/api/state").get_json()["language"] == "en"


def test_the_choice_survives_a_restart(client, new_app):
    set_language(client, "el")
    i18n.set_language("en")  # forget the in-memory copy: the database must remember
    new_app()
    assert i18n.language() == "el"


def test_untouched_starter_content_follows_the_language(client):
    en, el = db.STARTER_TOPICS["en"], db.STARTER_TOPICS["el"]
    deleted = client.get("/api/state").get_json()["topics"][1]
    client.delete(f"/api/topics/{deleted['id']}")
    client.post("/api/topics", json={"title": "Our own topic"})
    client.post("/api/topics", json={"title": el[2]})  # the Greek title already exists
    set_language(client, "el")
    titles = topic_titles(client)
    assert titles[0] == el[0]
    assert el[1] not in titles and en[1] not in titles  # a deleted topic does not come back
    assert en[2] in titles and titles.count(el[2]) == 1  # no duplicates
    assert "Our own topic" in titles
    assert client.get("/api/state").get_json()["content"]["brand_voice"] == db.STARTER_VOICE["el"]
    set_language(client, "en")
    assert topic_titles(client)[0] == en[0] and "Our own topic" in topic_titles(client)


def test_edited_voice_is_never_replaced(client):
    client.put("/api/content", json={"brand_voice": "Short and warm."})
    set_language(client, "el")
    assert client.get("/api/state").get_json()["content"]["brand_voice"] == "Short and warm."


def test_install_seeded_in_greek_follows_a_switch_to_english(app, client):
    with db.open_db(services(app).settings.db_path) as conn:
        conn.execute("UPDATE content_settings SET brand_voice = ?", (db.STARTER_VOICE["el"],))
        for en, el in zip(db.STARTER_TOPICS["en"], db.STARTER_TOPICS["el"]):
            conn.execute("UPDATE topics SET title = ? WHERE title = ?", (el, en))
    set_language(client, "en")
    assert topic_titles(client) == list(db.STARTER_TOPICS["en"])
    assert client.get("/api/state").get_json()["content"]["brand_voice"] == db.STARTER_VOICE["en"]


def test_an_install_from_before_the_switch_starts_in_english(app, new_app):
    with db.open_db(services(app).settings.db_path) as conn:
        conn.execute("DELETE FROM meta WHERE key = ?", (i18n.META_KEY,))
        conn.execute("UPDATE content_settings SET brand_voice = ?", (db.STARTER_VOICE["el"],))
        for en, el in zip(db.STARTER_TOPICS["en"], db.STARTER_TOPICS["el"]):
            conn.execute("UPDATE topics SET title = ? WHERE title = ?", (el, en))
    state = Client(new_app()).get("/api/state").get_json()
    assert state["language"] == "en"
    assert [t["title"] for t in state["topics"]] == list(db.STARTER_TOPICS["en"])
    assert state["content"]["brand_voice"] == db.STARTER_VOICE["en"]


def test_messages_written_by_the_scheduler_follow_the_language(app, client):
    set_language(client, "el")
    account = add_x(client)
    when = time.time() + 3600
    body = {"posts": [{"account_id": account["id"], "text": "Γεια"}], "scheduled_at": when}
    client.post("/api/posts", json=body)
    assert services(app).scheduler.tick(at=when + 7 * 3600) == 1
    failed = client.get("/api/posts?status=failed").get_json()["posts"][0]
    assert "δεν έτρεχε" in failed["error"]
