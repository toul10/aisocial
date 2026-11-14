"""SQLite storage: schema, connections and queries.

Connections run in autocommit mode; multi-statement changes use transaction().
Each thread (web request or scheduler) opens its own connection.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .i18n import DEFAULT_LANGUAGE, META_KEY as LANGUAGE_KEY, L

SCHEMA_VERSION = "1"

# Starter content for a new install, in the interface language. While nobody has edited it,
# it follows a language switch (see translate_starter_content).
STARTER_VOICE = {
    "en": """Style: friendly, clear and professional. Write like a person, not like a press release.
Rules:
- One main idea per post. Start with the most interesting point.
- Concrete examples instead of generalities.
- At most 1-2 relevant hashtags, only if they fit naturally.
- At most one emoji, and only if it really fits.
- No clickbait, no ALL CAPS, no made-up facts or numbers.""",
    "el": """Ύφος: φιλικό, καθαρό και επαγγελματικό. Γράφε σαν άνθρωπος, όχι σαν δελτίο τύπου.
Κανόνες:
- Μία βασική ιδέα ανά post. Ξεκίνα με το πιο ενδιαφέρον σημείο.
- Συγκεκριμένα παραδείγματα αντί για γενικότητες.
- Το πολύ 1-2 σχετικά hashtags, μόνο αν ταιριάζουν φυσικά.
- Το πολύ ένα emoji, και μόνο αν ταιριάζει πραγματικά.
- Χωρίς clickbait, χωρίς ΚΕΦΑΛΑΙΑ, χωρίς επινοημένα στοιχεία ή αριθμούς.""",
}

STARTER_TOPICS = {  # same order in both languages: item i is the translation of item i
    "en": (
        "A practical tip our audience can use today",
        "A common mistake in our field and how to avoid it",
        "Behind the scenes: how we work",
        "A question customers often ask us, with the answer",
        "A lesson we learned recently",
        "A trend in our industry worth watching",
    ),
    "el": (
        "Ένα πρακτικό tip που μπορεί να εφαρμόσει το κοινό μας σήμερα",
        "Ένα συνηθισμένο λάθος στον χώρο μας και πώς να το αποφύγεις",
        "Πίσω από τα παρασκήνια: πώς δουλεύουμε",
        "Μια ερώτηση που μας κάνουν συχνά οι πελάτες, με απάντηση",
        "Ένα μάθημα που πήραμε πρόσφατα",
        "Μια τάση στον κλάδο μας που αξίζει προσοχή",
    ),
}

POST_STATUSES = ("scheduled", "publishing", "published", "failed", "cancelled")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS app_secrets (
    name       TEXT PRIMARY KEY,
    value_enc  BLOB NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS content_settings (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    brand_name  TEXT NOT NULL DEFAULT '',
    about       TEXT NOT NULL DEFAULT '',
    brand_voice TEXT NOT NULL DEFAULT '',
    language    TEXT NOT NULL DEFAULT '',
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS topics (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS topics_title_unique ON topics (title COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL,
    name            TEXT NOT NULL,
    credentials_enc BLOB NOT NULL,
    status_json     TEXT NOT NULL DEFAULT '{}',
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS posts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER REFERENCES accounts (id) ON DELETE SET NULL,
    account_name TEXT NOT NULL,
    platform     TEXT NOT NULL,
    text         TEXT NOT NULL,
    image_id     TEXT,
    status       TEXT NOT NULL
                 CHECK (status IN ('scheduled', 'publishing', 'published', 'failed', 'cancelled')),
    scheduled_at REAL,
    published_at REAL,
    external_id  TEXT,
    external_url TEXT,
    error        TEXT,
    attempts     INTEGER NOT NULL DEFAULT 0,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS posts_due ON posts (status, scheduled_at);
CREATE TABLE IF NOT EXISTS oauth_states (
    state      TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
    return_to  TEXT NOT NULL DEFAULT 'settings',
    created_at REAL NOT NULL
);
"""


def now() -> float:
    return time.time()


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


@contextmanager
def open_db(path: Path | str) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open_db(path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        with transaction(conn):
            if conn.execute("SELECT 1 FROM content_settings WHERE id = 1").fetchone() is None:
                language = get_meta(conn, LANGUAGE_KEY)
                language = language if language in STARTER_VOICE else DEFAULT_LANGUAGE
                conn.execute(
                    "INSERT INTO content_settings (id, brand_voice, updated_at) VALUES (1, ?, ?)",
                    (STARTER_VOICE[language], now()),
                )
                conn.executemany(
                    "INSERT OR IGNORE INTO topics (title, created_at) VALUES (?, ?)",
                    [(t, now()) for t in STARTER_TOPICS[language]],
                )
            if not get_meta(conn, LANGUAGE_KEY):
                # First start, or an install from before the language switch (seeded in Greek):
                # record the default and bring untouched starter text in line with it.
                set_meta(conn, LANGUAGE_KEY, DEFAULT_LANGUAGE)
                translate_starter_content(conn, DEFAULT_LANGUAGE)
            conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )


# --- meta & app secrets -----------------------------------------------------

def get_meta(conn, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def get_secret(conn, name: str) -> bytes | None:
    row = conn.execute("SELECT value_enc FROM app_secrets WHERE name = ?", (name,)).fetchone()
    return bytes(row["value_enc"]) if row else None


def set_secret(conn, name: str, value_enc: bytes) -> None:
    conn.execute(
        "INSERT INTO app_secrets (name, value_enc, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT (name) DO UPDATE SET value_enc = excluded.value_enc, updated_at = excluded.updated_at",
        (name, value_enc, now()),
    )


def delete_secret(conn, name: str) -> None:
    conn.execute("DELETE FROM app_secrets WHERE name = ?", (name,))


# --- content & topics -------------------------------------------------------

def get_content(conn) -> dict:
    row = conn.execute(
        "SELECT brand_name, about, brand_voice, language FROM content_settings WHERE id = 1"
    ).fetchone()
    return dict(row) if row else {"brand_name": "", "about": "", "brand_voice": "", "language": ""}


def update_content(conn, **fields: str) -> None:
    allowed = {"brand_name", "about", "brand_voice", "language"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    assignments = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE content_settings SET {assignments}, updated_at = ? WHERE id = 1",
        (*fields.values(), now()),
    )


def translate_starter_content(conn, language: str) -> None:
    """Starter voice and topics that nobody has edited switch to `language`. Edited text stays as written.

    Matches the starter text of every language, so an install seeded in Greek still follows a switch.
    """
    if language not in STARTER_VOICE:
        return
    row = conn.execute("SELECT brand_voice FROM content_settings WHERE id = 1").fetchone()
    if row and row["brand_voice"] in STARTER_VOICE.values() and row["brand_voice"] != STARTER_VOICE[language]:
        conn.execute(
            "UPDATE content_settings SET brand_voice = ?, updated_at = ? WHERE id = 1",
            (STARTER_VOICE[language], now()),
        )
    renames = {}
    for other, titles in STARTER_TOPICS.items():
        if other != language:
            renames.update(zip(titles, STARTER_TOPICS[language]))
    rows = conn.execute("SELECT id, title FROM topics ORDER BY id").fetchall()
    taken = {r["title"].casefold() for r in rows}
    for r in rows:
        new = renames.get(r["title"])  # exact match: a starter topic nobody touched
        if new and new.casefold() not in taken:
            conn.execute("UPDATE topics SET title = ? WHERE id = ?", (new, r["id"]))
            taken = (taken - {r["title"].casefold()}) | {new.casefold()}


def list_topics(conn, active_only: bool = False) -> list[dict]:
    sql = "SELECT id, title, active FROM topics"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY id"
    return [dict(r) | {"active": bool(r["active"])} for r in conn.execute(sql)]


def add_topic(conn, title: str) -> int | None:
    """Returns the new topic id, or None if the topic already exists.

    SQLite's NOCASE only folds ASCII, so Greek titles are compared with casefold().
    """
    key = title.casefold()
    if any(row["title"].casefold() == key for row in conn.execute("SELECT title FROM topics")):
        return None
    try:
        cur = conn.execute("INSERT INTO topics (title, created_at) VALUES (?, ?)", (title, now()))
    except sqlite3.IntegrityError:
        return None
    return cur.lastrowid


def set_topic_active(conn, topic_id: int, active: bool) -> bool:
    cur = conn.execute("UPDATE topics SET active = ? WHERE id = ?", (int(active), topic_id))
    return cur.rowcount == 1


def delete_topic(conn, topic_id: int) -> bool:
    return conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,)).rowcount == 1


# --- accounts ---------------------------------------------------------------

def _account(row) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    data["status"] = json.loads(data.pop("status_json") or "{}")
    data["credentials_enc"] = bytes(data["credentials_enc"])
    return data


def list_accounts(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM accounts ORDER BY platform, name, id")
    return [_account(r) for r in rows]


def get_account(conn, account_id: int) -> dict | None:
    return _account(conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone())


def create_account(conn, platform: str, name: str, credentials_enc: bytes, status: dict | None = None) -> int:
    ts = now()
    cur = conn.execute(
        "INSERT INTO accounts (platform, name, credentials_enc, status_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (platform, name, credentials_enc, json.dumps(status or {}), ts, ts),
    )
    return cur.lastrowid


def update_account(conn, account_id: int, *, name: str | None = None,
                   credentials_enc: bytes | None = None, status: dict | None = None) -> None:
    sets, params = [], []
    if name is not None:
        sets.append("name = ?")
        params.append(name)
    if credentials_enc is not None:
        sets.append("credentials_enc = ?")
        params.append(credentials_enc)
    if status is not None:
        sets.append("status_json = ?")
        params.append(json.dumps(status))
    if not sets:
        return
    sets.append("updated_at = ?")
    params.append(now())
    conn.execute(f"UPDATE accounts SET {', '.join(sets)} WHERE id = ?", (*params, account_id))


def delete_account(conn, account_id: int) -> int:
    """Deletes the account and cancels its scheduled posts. Returns cancelled count."""
    with transaction(conn):
        cancelled = conn.execute(
            "UPDATE posts SET status = 'cancelled', error = ?, updated_at = ? "
            "WHERE account_id = ? AND status = 'scheduled'",
            (L("The account was deleted.", "Ο λογαριασμός διαγράφηκε."), now(), account_id),
        ).rowcount
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    return cancelled


# --- posts --------------------------------------------------------------------

def _post(row) -> dict | None:
    return dict(row) if row is not None else None


def create_post(conn, *, account_id: int, account_name: str, platform: str, text: str,
                image_id: str | None, status: str, scheduled_at: float | None) -> int:
    ts = now()
    cur = conn.execute(
        "INSERT INTO posts (account_id, account_name, platform, text, image_id, status, "
        "scheduled_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (account_id, account_name, platform, text, image_id, status, scheduled_at, ts, ts),
    )
    return cur.lastrowid


def get_post(conn, post_id: int) -> dict | None:
    return _post(conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone())


def list_posts(conn, status: str | None = None, limit: int = 200) -> list[dict]:
    if status in ("scheduled", "publishing"):
        # Soonest first, so the limit never hides the posts that go out next.
        rows = conn.execute(
            "SELECT * FROM posts WHERE status = ? ORDER BY COALESCE(scheduled_at, created_at) ASC, id ASC LIMIT ?",
            (status, limit),
        )
    elif status:
        rows = conn.execute(
            "SELECT * FROM posts WHERE status = ? ORDER BY COALESCE(published_at, updated_at) DESC, id DESC LIMIT ?",
            (status, limit),
        )
    else:
        rows = conn.execute(
            "SELECT * FROM posts ORDER BY CASE status WHEN 'scheduled' THEN 0 ELSE 1 END, "
            "CASE status WHEN 'scheduled' THEN scheduled_at END ASC, "
            "COALESCE(published_at, updated_at) DESC, id DESC LIMIT ?",
            (limit,),
        )
    return [dict(r) for r in rows]


def claim_post(conn, post_id: int, from_statuses: tuple[str, ...]) -> bool:
    """Atomically move a post to 'publishing'. False if another worker got it first."""
    marks = ", ".join("?" for _ in from_statuses)
    cur = conn.execute(
        f"UPDATE posts SET status = 'publishing', attempts = attempts + 1, error = NULL, updated_at = ? "
        f"WHERE id = ? AND status IN ({marks})",
        (now(), post_id, *from_statuses),
    )
    return cur.rowcount == 1


def finish_post(conn, post_id: int, *, status: str, error: str | None = None,
                external_id: str | None = None, external_url: str | None = None) -> None:
    conn.execute(
        "UPDATE posts SET status = ?, error = ?, external_id = COALESCE(?, external_id), "
        "external_url = COALESCE(?, external_url), "
        "published_at = CASE WHEN ? = 'published' THEN ? ELSE published_at END, updated_at = ? "
        "WHERE id = ?",
        (status, error, external_id, external_url, status, now(), now(), post_id),
    )


def due_posts(conn, at: float) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM posts WHERE status = 'scheduled' AND scheduled_at <= ? ORDER BY scheduled_at, id",
        (at,),
    )
    return [dict(r) for r in rows]


def set_post_status(conn, post_id: int, status: str, from_statuses: tuple[str, ...],
                    error: str | None = None) -> bool:
    marks = ", ".join("?" for _ in from_statuses)
    cur = conn.execute(
        f"UPDATE posts SET status = ?, error = ?, updated_at = ? WHERE id = ? AND status IN ({marks})",
        (status, error, now(), post_id, *from_statuses),
    )
    return cur.rowcount == 1


def update_scheduled_post(conn, post_id: int, *, text: str | None = None,
                          scheduled_at: float | None = None) -> bool:
    """Edit a post that is still waiting. False if it is no longer 'scheduled'."""
    sets, params = [], []
    if text is not None:
        sets.append("text = ?")
        params.append(text)
    if scheduled_at is not None:
        sets.append("scheduled_at = ?")
        params.append(scheduled_at)
    sets.append("updated_at = ?")
    params.append(now())
    cur = conn.execute(
        f"UPDATE posts SET {', '.join(sets)} WHERE id = ? AND status = 'scheduled'", (*params, post_id)
    )
    return cur.rowcount == 1


def post_counts(conn) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM posts GROUP BY status")
    return {row["status"]: row["n"] for row in rows}


# --- dashboard queries ---

def scheduled_until(conn, until: float, limit: int = 200) -> list[dict]:
    """Scheduled posts due before `until`, oldest first. Includes overdue ones (the app was closed)."""
    rows = conn.execute(
        "SELECT * FROM posts WHERE status = 'scheduled' AND scheduled_at <= ? ORDER BY scheduled_at, id LIMIT ?",
        (until, limit),
    )
    return [dict(r) for r in rows]


def next_scheduled_at(conn, after: float) -> float | None:
    row = conn.execute(
        "SELECT MIN(scheduled_at) AS at FROM posts WHERE status = 'scheduled' AND scheduled_at >= ?", (after,)
    ).fetchone()
    return row["at"] if row else None


def recent_results(conn, limit: int = 6) -> list[dict]:
    """The latest published or failed posts, newest first."""
    rows = conn.execute(
        "SELECT * FROM posts WHERE status IN ('published', 'failed') "
        "ORDER BY COALESCE(published_at, updated_at) DESC, id DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in rows]


def published_since(conn, since: float) -> list[dict]:
    """Platform and time of every post published after `since` (for the activity charts)."""
    rows = conn.execute(
        "SELECT platform, published_at FROM posts WHERE status = 'published' AND published_at >= ? ORDER BY published_at",
        (since,),
    )
    return [dict(r) for r in rows]


def delete_post(conn, post_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM posts WHERE id = ? AND status IN ('published', 'failed', 'cancelled')",
        (post_id,),
    )
    return cur.rowcount == 1


def recover_interrupted(conn) -> int:
    """Posts left in 'publishing' (app stopped mid-publish) become failed, never auto-retried."""
    return conn.execute(
        "UPDATE posts SET status = 'failed', error = ?, updated_at = ? WHERE status = 'publishing'",
        (
            L(
                "AI Social stopped while publishing. Check the platform before you retry, "
                "because the post may have gone out.",
                "Το πρόγραμμα σταμάτησε την ώρα της δημοσίευσης. Έλεγξε την πλατφόρμα "
                "πριν κάνεις retry, γιατί το post ίσως δημοσιεύτηκε.",
            ),
            now(),
        ),
    ).rowcount


def count_rows(conn, table: str) -> int:
    if table not in ("accounts", "topics", "posts"):
        raise ValueError(table)
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# --- oauth states -------------------------------------------------------------

def save_oauth_state(conn, state: str, account_id: int, return_to: str = "settings") -> None:
    conn.execute("DELETE FROM oauth_states WHERE created_at < ?", (now() - 3600,))
    conn.execute(
        "INSERT INTO oauth_states (state, account_id, return_to, created_at) VALUES (?, ?, ?, ?)",
        (state, account_id, return_to, now()),
    )


def pop_oauth_state(conn, state: str, max_age: float = 600) -> tuple[int, str] | None:
    """Consume a state value (single use). Returns (account_id, return_to) or None."""
    with transaction(conn):
        row = conn.execute(
            "SELECT account_id, return_to, created_at FROM oauth_states WHERE state = ?", (state,)
        ).fetchone()
        conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
    if row is None or now() - row["created_at"] > max_age:
        return None
    return row["account_id"], row["return_to"]
