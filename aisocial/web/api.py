"""JSON API used by the browser UI.

Every response is {"ok": true, ...} or {"ok": false, "error": "<message for the user>"}.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict
from datetime import datetime

from flask import Blueprint, jsonify, request, url_for

from .. import db, i18n, media
from ..ai import AIError
from ..ai.service import mask
from ..config import TEXT_PROVIDERS
from ..crypto import DecryptionError
from ..guides import ai_guides, platform_guides
from ..i18n import L
from ..platforms import PlatformError, redact
from . import get_db, services

bp = Blueprint("api", __name__, url_prefix="/api")

LENGTHS = ("short", "medium", "long")
MIN_SCHEDULE_LEAD = 30  # seconds
MAX_SCHEDULE_DAYS = 366
MAX_POST_TEXT = 100_000
PROVIDER_LABELS = {"anthropic": "Claude (Anthropic)", "openai": "OpenAI"}
CONTENT_FIELDS = {  # field: ((English label, Greek label), max length)
    "brand_name": (("Name", "Όνομα"), 100),
    "about": (("What you do / what you sell", "Τι κάνεις / τι πουλάς"), 1500),
    "brand_voice": (("Writing style", "Ύφος γραφής"), 4000),
    "language": (("Language", "Γλώσσα"), 40),
}


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@bp.errorhandler(ApiError)
def _api_error(exc: ApiError):
    return jsonify(ok=False, error=str(exc)), exc.status


@bp.errorhandler(AIError)
def _ai_error(exc: AIError):
    return jsonify(ok=False, error=str(exc)), 400


@bp.errorhandler(media.MediaError)
def _media_error(exc: media.MediaError):
    return jsonify(ok=False, error=str(exc)), 400


@bp.errorhandler(DecryptionError)
def _decryption_error(exc: DecryptionError):
    return jsonify(ok=False, error=str(exc)), 500


# --- input helpers -------------------------------------------------------------

def body() -> dict:
    data = request.get_json(silent=True)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ApiError(L("Invalid request.", "Μη έγκυρο αίτημα."))
    return data


def text_field(data: dict, name: str, label: str, *, max_len: int, required: bool = False) -> str:
    value = data.get(name)
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ApiError(L(f"The field “{label}” is not valid.", f"Το πεδίο «{label}» δεν είναι έγκυρο."))
    value = value.strip()
    if required and not value:
        raise ApiError(L(f"Fill in the field “{label}”.", f"Συμπλήρωσε το πεδίο «{label}»."))
    if len(value) > max_len:
        raise ApiError(L(
            f"The field “{label}” is too long (up to {max_len} characters).",
            f"Το πεδίο «{label}» είναι πολύ μεγάλο (έως {max_len} χαρακτήρες).",
        ))
    return value


def as_id(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def fmt_date(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")


# --- accounts ------------------------------------------------------------------

def _platform(key):
    platform = services().platforms.get(key) if isinstance(key, str) else None
    if platform is None:
        raise ApiError(L("Unknown platform.", "Άγνωστη πλατφόρμα."))
    return platform


def _creds(account: dict) -> dict | None:
    try:
        return services().box.decrypt_json(account["credentials_enc"])
    except DecryptionError:
        return None


def account_readiness(platform, creds: dict | None) -> tuple[bool, str | None]:
    """Can this account publish right now? Returns (ready, reason if not)."""
    if creds is None:
        return False, L(
            "The saved details cannot be read (did APP_SECRET change?). Enter them again.",
            "Τα αποθηκευμένα στοιχεία δεν διαβάζονται (άλλαξε το APP_SECRET;). Βάλ' τα ξανά.",
        )
    missing = platform.missing_fields(creds)
    if missing:
        return False, L("Missing: ", "Λείπουν: ") + ", ".join(missing) + "."
    if platform.oauth:
        if not creds.get("access_token"):
            return False, L(
                f"Not connected yet. Press “Connect {platform.label}”.",
                f"Δεν έχει συνδεθεί ακόμα. Πάτα «Σύνδεση {platform.label}».",
            )
        expires_at = float(creds.get("expires_at") or 0)
        if expires_at and expires_at < db.now() + 60:
            return False, L(
                "The connection has expired. Press “Reconnect” (Settings → Accounts).",
                "Η σύνδεση έληξε. Πάτα «Επανασύνδεση» (Ρυθμίσεις → Λογαριασμοί).",
            )
    return True, None


def account_out(account: dict) -> dict:
    """Account data for the UI. Secret values never leave the server."""
    platform = services().platforms.get(account["platform"])
    creds = _creds(account)
    if platform is None:
        ready, problem, fields = False, L("Unknown platform.", "Άγνωστη πλατφόρμα."), {}
    else:
        ready, problem = account_readiness(platform, creds)
        fields = {}
        for field in platform.fields:
            value = str((creds or {}).get(field.name) or "")
            fields[field.name] = {
                "set": bool(value),
                "value": None if field.secret else value,
                "hint": mask(value) if field.secret else None,
            }
    status = account["status"] or {}
    oauth = bool(platform and platform.oauth)
    return {
        "id": account["id"],
        "platform": account["platform"],
        "platform_label": platform.label if platform else account["platform"],
        "name": account["name"],
        "fields": fields,
        "ready": ready,
        "problem": problem,
        "oauth": oauth,
        "connected": bool(creds and creds.get("access_token")) if oauth else None,
        "connect_url": url_for("oauth.linkedin_start", account_id=account["id"]) if oauth else None,
        "expires_at": (creds or {}).get("expires_at") if oauth else None,
        "check": {
            "ok": status.get("ok"),
            "message": status.get("error") if status.get("ok") is False else None,
            "username": status.get("username"),
            "checked_at": status.get("checked_at"),
        },
    }


def _credentials_input(platform, data: dict) -> dict:
    raw = data.get("credentials") or {}
    if not isinstance(raw, dict):
        raise ApiError(L("Invalid account details.", "Μη έγκυρα στοιχεία λογαριασμού."))
    creds = {}
    for field in platform.fields:
        value = raw.get(field.name)
        if value is None:
            continue
        if not isinstance(value, str) or len(value) > 4000:
            raise ApiError(L(f"Invalid value in “{field.label}”.", f"Μη έγκυρη τιμή στο «{field.label}»."))
        if value.strip():
            creds[field.name] = value.strip()
    return creds


def _validated(platform, creds: dict) -> dict:
    try:
        creds = platform.clean_credentials(creds)
    except PlatformError as exc:
        raise ApiError(str(exc)) from exc
    missing = platform.missing_fields(creds)
    if missing:
        raise ApiError(L("Fill in: ", "Συμπλήρωσε: ") + ", ".join(missing) + ".")
    return creds


def _get_account(account_id: int) -> dict:
    account = db.get_account(get_db(), account_id)
    if account is None:
        raise ApiError(L("Account not found.", "Ο λογαριασμός δεν βρέθηκε."), 404)
    return account


def _platforms_out() -> list[dict]:
    s = services()
    guides = platform_guides(s.settings)
    return [dict(p.describe(), guide=guides.get(p.key)) for p in s.platforms.values()]


# --- overview & setup ------------------------------------------------------------

@bp.get("/state")
def state():
    from .. import __version__

    s = services()
    conn = get_db()
    return jsonify(
        ok=True,
        version=__version__,
        language=i18n.language(),
        setup_completed=db.get_meta(conn, "setup_completed") == "1",
        public_url=s.settings.public_url,
        password_protected=bool(s.settings.password),
        ai=s.ai.status(),
        ai_guides=ai_guides(),
        platforms=_platforms_out(),
        accounts=[account_out(a) for a in db.list_accounts(conn)],
        content=db.get_content(conn),
        topics=db.list_topics(conn),
    )


@bp.post("/setup/complete")
def setup_complete():
    db.set_meta(get_db(), "setup_completed", "1")
    return jsonify(ok=True)


@bp.put("/ui")
def ui_update():
    """Switch the interface language. The page reloads to show it."""
    language = body().get("language")
    if language not in i18n.LANGUAGES:
        raise ApiError(L("Unknown language.", "Άγνωστη γλώσσα."))
    conn = get_db()
    with db.transaction(conn):
        db.set_meta(conn, i18n.META_KEY, language)
        db.translate_starter_content(conn, language)
    i18n.set_language(language)
    return jsonify(ok=True, language=language)


# --- AI keys ---------------------------------------------------------------------

def _check_key_shape(provider: str, value: str) -> None:
    label = PROVIDER_LABELS[provider]
    if len(value) < 20 or len(value) > 500 or any(ch.isspace() for ch in value):
        raise ApiError(L(
            f"This {label} key does not look right. Copy it again, all of it.",
            f"Το {label} key δεν μοιάζει σωστό. Αντέγραψέ το ξανά, ολόκληρο.",
        ))
    if provider == "anthropic" and value.startswith("sk-") and not value.startswith("sk-ant-"):
        raise ApiError(L(
            "This looks like an OpenAI key. A Claude key starts with sk-ant-.",
            "Αυτό μοιάζει με OpenAI key. Το Claude key ξεκινά με sk-ant-.",
        ))
    if provider == "openai" and value.startswith("sk-ant-"):
        raise ApiError(L(
            "This is a Claude (Anthropic) key. Put it in the Claude field.",
            "Αυτό είναι Claude (Anthropic) key. Βάλ' το στο πεδίο του Claude.",
        ))


@bp.get("/ai")
def ai_get():
    return jsonify(ok=True, ai=services().ai.status(), guides=ai_guides())


@bp.put("/ai")
def ai_update():
    data = body()
    s = services()
    updates: dict[str, str | None] = {}
    for provider in PROVIDER_LABELS:
        name = f"{provider}_api_key"
        if name not in data:
            continue
        value = data[name]
        if value is None:
            updates[name] = None  # remove the saved key
            continue
        if not isinstance(value, str):
            raise ApiError(L("Invalid key.", "Μη έγκυρο key."))
        value = value.strip()
        if not value:
            continue  # empty field: keep the saved key
        _check_key_shape(provider, value)
        updates[name] = value
    choice = data.get("text_provider")
    if choice is not None and choice not in TEXT_PROVIDERS:
        raise ApiError(L("Invalid AI choice.", "Μη έγκυρη επιλογή AI."))
    conn = get_db()
    with db.transaction(conn):
        for name, value in updates.items():
            if value is None:
                db.delete_secret(conn, name)
            else:
                db.set_secret(conn, name, s.box.encrypt_text(value))
        if choice is not None:
            db.set_meta(conn, "ai_text_provider", choice)
    s.ai.invalidate()
    return jsonify(ok=True, ai=s.ai.status())


@bp.post("/ai/check")
def ai_check():
    s = services()
    return jsonify(ok=True, results=s.ai.check(), ai=s.ai.status())


# --- brand & topics ----------------------------------------------------------------

@bp.put("/content")
def content_update():
    data = body()
    fields = {
        name: text_field(data, name, L(*labels), max_len=max_len)
        for name, (labels, max_len) in CONTENT_FIELDS.items()
        if name in data
    }
    conn = get_db()
    db.update_content(conn, **fields)
    return jsonify(ok=True, content=db.get_content(conn))


def _topic_title(value) -> str:
    if not isinstance(value, str):
        raise ApiError(L("Invalid topic.", "Μη έγκυρο θέμα."))
    title = " ".join(value.split())
    if len(title) > 200:
        raise ApiError(L("The topic is too long (up to 200 characters).", "Το θέμα είναι πολύ μεγάλο (έως 200 χαρακτήρες)."))
    return title


@bp.post("/topics")
def topics_add():
    data = body()
    raw = data.get("titles") if "titles" in data else [data.get("title")]
    if not isinstance(raw, list):
        raise ApiError(L("Invalid list of topics.", "Μη έγκυρη λίστα θεμάτων."))
    titles = [t for t in (_topic_title(v) for v in raw[:100]) if t]
    if not titles:
        raise ApiError(L("Write a topic.", "Γράψε ένα θέμα."))
    conn = get_db()
    added = 0
    with db.transaction(conn):
        for title in titles:
            if db.add_topic(conn, title) is not None:
                added += 1
    return jsonify(ok=True, added=added, skipped=len(titles) - added, topics=db.list_topics(conn)), 201


@bp.patch("/topics/<int:topic_id>")
def topics_update(topic_id: int):
    active = body().get("active")
    if not isinstance(active, bool):
        raise ApiError(L("Invalid value.", "Μη έγκυρη τιμή."))
    conn = get_db()
    if not db.set_topic_active(conn, topic_id, active):
        raise ApiError(L("Topic not found.", "Το θέμα δεν βρέθηκε."), 404)
    return jsonify(ok=True, topics=db.list_topics(conn))


@bp.delete("/topics/<int:topic_id>")
def topics_delete(topic_id: int):
    conn = get_db()
    if not db.delete_topic(conn, topic_id):
        raise ApiError(L("Topic not found.", "Το θέμα δεν βρέθηκε."), 404)
    return jsonify(ok=True, topics=db.list_topics(conn))


# --- accounts -----------------------------------------------------------------------

@bp.get("/accounts")
def accounts_list():
    return jsonify(ok=True, accounts=[account_out(a) for a in db.list_accounts(get_db())])


@bp.post("/accounts")
def accounts_create():
    data = body()
    s = services()
    platform = _platform(data.get("platform"))
    name = text_field(data, "name", L("Name", "Όνομα"), max_len=80) or platform.label
    creds = _validated(platform, _credentials_input(platform, data))
    conn = get_db()
    account_id = db.create_account(conn, platform.key, name, s.box.encrypt_json(creds))
    return jsonify(ok=True, account=account_out(db.get_account(conn, account_id))), 201


@bp.put("/accounts/<int:account_id>")
def accounts_update(account_id: int):
    data = body()
    s = services()
    conn = get_db()
    account = _get_account(account_id)
    platform = _platform(account["platform"])
    name = text_field(data, "name", L("Name", "Όνομα"), max_len=80) if "name" in data else ""
    changes = _credentials_input(platform, data)  # empty fields keep the saved value
    creds_enc = status = None
    if changes:
        current = _creds(account) or {}  # unreadable: start over with what was typed
        keep_status = False
        if platform.oauth:
            if changes.get("client_id", current.get("client_id")) != current.get("client_id"):
                # A token belongs to the app that issued it.
                current = {k: v for k, v in current.items() if k in {f.name for f in platform.fields}}
            else:
                keep_status = bool(current.get("access_token"))
        creds_enc = s.box.encrypt_json(_validated(platform, {**current, **changes}))
        status = None if keep_status else {}
    db.update_account(conn, account_id, name=name or None, credentials_enc=creds_enc, status=status)
    return jsonify(ok=True, account=account_out(db.get_account(conn, account_id)))


@bp.delete("/accounts/<int:account_id>")
def accounts_delete(account_id: int):
    _get_account(account_id)
    cancelled = db.delete_account(get_db(), account_id)
    return jsonify(ok=True, cancelled=cancelled)


@bp.post("/accounts/<int:account_id>/verify")
def accounts_verify(account_id: int):
    conn = get_db()
    account = _get_account(account_id)
    platform = _platform(account["platform"])
    creds = _creds(account)
    ready, problem = account_readiness(platform, creds)
    if not ready:
        return jsonify(ok=True, verified=False, message=problem, account=account_out(account))
    try:
        info = platform.verify(creds)
    except PlatformError as exc:
        message = redact(str(exc), creds.values())
        status = dict(account["status"], ok=False, error=message, checked_at=db.now())
        db.update_account(conn, account_id, status=status)
        return jsonify(ok=True, verified=False, message=message,
                       account=account_out(db.get_account(conn, account_id)))
    username = info.get("username") or account["status"].get("username")
    db.update_account(conn, account_id, status={
        "ok": True, "error": None, "checked_at": db.now(), "username": username,
    })
    message = (
        L(f"All good. Connected as {username}.", f"Όλα καλά. Συνδεδεμένο ως {username}.")
        if username else L("All good.", "Όλα καλά.")
    )
    return jsonify(ok=True, verified=True, message=message,
                   account=account_out(db.get_account(conn, account_id)))


# --- AI generation ----------------------------------------------------------------------

@bp.post("/generate/text")
def generate_text():
    data = body()
    conn = get_db()
    platform = _platform(data.get("platform"))
    length = data.get("length") or "medium"
    if length not in LENGTHS:
        raise ApiError(L("Invalid length.", "Μη έγκυρο μήκος."))
    topic = text_field(data, "topic", L("Topic", "Θέμα"), max_len=500)
    instructions = text_field(data, "instructions", L("Instructions", "Οδηγίες"), max_len=1500)
    if not topic:
        active = db.list_topics(conn, active_only=True)
        if not active:
            raise ApiError(L(
                "Write a topic, or add topics in Settings, under “Business and topics”.",
                "Γράψε ένα θέμα ή πρόσθεσε θέματα στις Ρυθμίσεις, στο «Επιχείρηση και θέματα».",
            ))
        topic = random.choice(active)["title"]
    draft = services().ai.write_post(
        topic=topic, platform=platform, length=length,
        content=db.get_content(conn), instructions=instructions,
    )
    return jsonify(ok=True, draft=dict(asdict(draft), platform=platform.key))


@bp.post("/generate/topics")
def generate_topics():
    count = body().get("count", 10)
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 20:
        raise ApiError(L("Invalid number of topics.", "Μη έγκυρος αριθμός θεμάτων."))
    conn = get_db()
    existing = {t["title"].casefold() for t in db.list_topics(conn)}
    suggestions = services().ai.suggest_topics(db.get_content(conn), count)
    return jsonify(ok=True, topics=[t for t in suggestions if t.casefold() not in existing])


@bp.post("/generate/image-prompt")
def generate_image_prompt():
    text = text_field(body(), "text", L("Text", "Κείμενο"), max_len=MAX_POST_TEXT, required=True)
    return jsonify(ok=True, prompt=services().ai.image_prompt(text))


def _image_out(image_id: str) -> dict:
    return {"id": image_id, "url": url_for("pages.media_file", image_id=image_id)}


@bp.post("/generate/image")
def generate_image():
    prompt = text_field(body(), "prompt", L("Image description", "Περιγραφή εικόνας"), max_len=3000, required=True)
    s = services()
    image_id = media.save_image(s.settings.media_dir, s.ai.generate_image(prompt))
    return jsonify(ok=True, image=_image_out(image_id)), 201


@bp.post("/images")
def images_upload():
    upload = request.files.get("file")
    if upload is None:
        raise ApiError(L("Choose an image.", "Διάλεξε μια εικόνα."))
    image_id = media.save_image(services().settings.media_dir, upload.read(media.MAX_IMAGE_BYTES + 1))
    return jsonify(ok=True, image=_image_out(image_id)), 201


# --- posts ------------------------------------------------------------------------------

POST_KEYS = (
    "id", "account_id", "account_name", "platform", "text", "image_id", "status",
    "scheduled_at", "published_at", "external_url", "error", "created_at", "updated_at",
)


def post_out(post: dict) -> dict:
    s = services()
    platform = s.platforms.get(post["platform"])
    image_ok = bool(post["image_id"]) and media.image_path(s.settings.media_dir, post["image_id"]) is not None
    return dict(
        {k: post[k] for k in POST_KEYS},
        platform_label=platform.label if platform else post["platform"],
        image_url=url_for("pages.media_file", image_id=post["image_id"]) if image_ok else None,
        max_chars=platform.max_chars if platform else None,
    )


def _get_post(post_id: int) -> dict:
    post = db.get_post(get_db(), post_id)
    if post is None:
        raise ApiError(L("Post not found.", "Το post δεν βρέθηκε."), 404)
    return post


def _schedule_time(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ApiError(L("Invalid time.", "Μη έγκυρη ώρα."))
    now = db.now()
    if value < now + MIN_SCHEDULE_LEAD:
        raise ApiError(L(
            "That time has already passed. Choose a future time or “Publish now”.",
            "Η ώρα που διάλεξες έχει περάσει. Διάλεξε μελλοντική ώρα ή «Δημοσίευση τώρα».",
        ))
    if value > now + MAX_SCHEDULE_DAYS * 86400:
        raise ApiError(L("You can schedule up to one year ahead.", "Μπορείς να προγραμματίσεις έως έναν χρόνο μπροστά."))
    return float(value)


def _post_text(data: dict, platform) -> str:
    label = L(f"Text for {platform.label}", f"Κείμενο για {platform.label}")
    text = text_field(data, "text", label, max_len=MAX_POST_TEXT, required=True)
    count = platform.count(text)
    if count > platform.max_chars:
        raise ApiError(L(
            f"The text for {platform.label} has {count} characters; the limit is {platform.max_chars}.",
            f"Το κείμενο για {platform.label} έχει {count} χαρακτήρες, ενώ το όριο είναι {platform.max_chars}.",
        ))
    return text


@bp.post("/posts")
def posts_create():
    """Body: {"posts": [{"account_id": 1, "text": "..."}, ...], "image_id": null, "scheduled_at": null}.

    scheduled_at null publishes now; a Unix time schedules. Everything is
    validated before anything is saved or published.
    """
    data = body()
    s = services()
    conn = get_db()
    items = data.get("posts")
    if not isinstance(items, list) or not items:
        raise ApiError(L("Choose at least one account.", "Διάλεξε τουλάχιστον έναν λογαριασμό."))
    if len(items) > 20:
        raise ApiError(L("Up to 20 accounts per post.", "Έως 20 λογαριασμοί σε κάθε δημοσίευση."))
    scheduled_at = _schedule_time(data.get("scheduled_at"))
    image_id = data.get("image_id") or None
    if image_id is not None and (
        not isinstance(image_id, str) or media.image_path(s.settings.media_dir, image_id) is None
    ):
        raise ApiError(L("Image not found. Upload it again.", "Η εικόνα δεν βρέθηκε. Ανέβασέ την ξανά."))

    planned, seen = [], set()
    for item in items:
        account_id = as_id(item.get("account_id")) if isinstance(item, dict) else None
        if account_id is None:
            raise ApiError(L("Invalid account.", "Μη έγκυρος λογαριασμός."))
        if account_id in seen:
            raise ApiError(L("The same account was chosen twice.", "Ο ίδιος λογαριασμός επιλέχθηκε δύο φορές."))
        seen.add(account_id)
        account = _get_account(account_id)
        platform = _platform(account["platform"])
        creds = _creds(account)
        ready, problem = account_readiness(platform, creds)
        if not ready:
            raise ApiError(f"{account['name']} ({platform.label}): {problem}")
        text = _post_text(item, platform)
        expires_at = float(creds.get("expires_at") or 0) if platform.oauth else 0
        if scheduled_at and expires_at and expires_at < scheduled_at:
            raise ApiError(L(
                f"{account['name']}: the {platform.label} connection expires on {fmt_date(expires_at)}, before "
                "the publishing time. Press “Reconnect” (Settings → Accounts), then schedule.",
                f"{account['name']}: η σύνδεση {platform.label} λήγει στις {fmt_date(expires_at)}, πριν "
                "την ώρα δημοσίευσης. Πάτα «Επανασύνδεση» (Ρυθμίσεις → Λογαριασμοί) και μετά προγραμμάτισε.",
            ))
        planned.append((account, platform, text))

    status = "scheduled" if scheduled_at else "publishing"
    with db.transaction(conn):
        ids = [
            db.create_post(
                conn, account_id=account["id"], account_name=account["name"], platform=platform.key,
                text=text, image_id=image_id, status=status, scheduled_at=scheduled_at,
            )
            for account, platform, text in planned
        ]
    if scheduled_at is None:
        # Rows start in 'publishing', so the scheduler never touches them.
        for post_id in ids:
            s.publisher.run_claimed(conn, post_id)
    return jsonify(ok=True, posts=[post_out(db.get_post(conn, i)) for i in ids]), 201


@bp.get("/posts")
def posts_list():
    status = request.args.get("status") or None
    if status is not None and status not in db.POST_STATUSES:
        raise ApiError(L("Invalid filter.", "Μη έγκυρο φίλτρο."))
    conn = get_db()
    return jsonify(
        ok=True,
        posts=[post_out(p) for p in db.list_posts(conn, status)],
        counts=db.post_counts(conn),
    )


DASHBOARD_AHEAD_DAYS = 8  # the week view shows 7 days; one more covers any time zone
DASHBOARD_HISTORY_DAYS = 92  # 12 full weeks plus the current one


@bp.get("/dashboard")
def dashboard():
    """Everything the home page shows. Days and weeks are bucketed in the browser, in local time."""
    conn = get_db()
    now = db.now()
    return jsonify(
        ok=True,
        now=now,
        counts=db.post_counts(conn),
        next_at=db.next_scheduled_at(conn, now),
        upcoming=[post_out(p) for p in db.scheduled_until(conn, now + DASHBOARD_AHEAD_DAYS * 86400)],
        recent=[post_out(p) for p in db.recent_results(conn)],
        published=[
            {"platform": row["platform"], "at": row["published_at"]}
            for row in db.published_since(conn, now - DASHBOARD_HISTORY_DAYS * 86400)
        ],
    )


@bp.patch("/posts/<int:post_id>")
def posts_update(post_id: int):
    data = body()
    conn = get_db()
    post = _get_post(post_id)
    if post["status"] != "scheduled":
        raise ApiError(L("Only scheduled posts can be changed.", "Αλλάζουν μόνο τα προγραμματισμένα posts."), 409)
    platform = _platform(post["platform"])
    text = _post_text(data, platform) if "text" in data else None
    scheduled_at = None
    if "scheduled_at" in data:
        scheduled_at = _schedule_time(data["scheduled_at"])
        if scheduled_at is None:
            raise ApiError(L("Choose a time.", "Διάλεξε ώρα."))
    if not db.update_scheduled_post(conn, post_id, text=text, scheduled_at=scheduled_at):
        raise ApiError(L("The post was just published or changed. Reload the page.", "Το post μόλις δημοσιεύτηκε ή άλλαξε. Ανανέωσε τη σελίδα."), 409)
    return jsonify(ok=True, post=post_out(db.get_post(conn, post_id)))


@bp.post("/posts/<int:post_id>/cancel")
def posts_cancel(post_id: int):
    conn = get_db()
    _get_post(post_id)
    if not db.set_post_status(conn, post_id, "cancelled", ("scheduled",)):
        raise ApiError(L("Only scheduled posts can be cancelled.", "Ακυρώνονται μόνο τα προγραμματισμένα posts."), 409)
    return jsonify(ok=True, post=post_out(db.get_post(conn, post_id)))


@bp.post("/posts/<int:post_id>/publish")
def posts_publish(post_id: int):
    conn = get_db()
    post = _get_post(post_id)
    allowed = ("scheduled", "failed", "cancelled")
    if post["status"] not in allowed:
        raise ApiError(L("This post is being published or is already published.", "Αυτό το post δημοσιεύεται ήδη ή έχει δημοσιευτεί."), 409)
    if not post["account_id"] or db.get_account(conn, post["account_id"]) is None:
        raise ApiError(L("The account of this post has been deleted.", "Ο λογαριασμός αυτού του post έχει διαγραφεί."), 409)
    result = services().publisher.publish(conn, post_id, from_statuses=allowed)
    return jsonify(ok=True, post=post_out(result))


@bp.delete("/posts/<int:post_id>")
def posts_delete(post_id: int):
    _get_post(post_id)
    if not db.delete_post(get_db(), post_id):
        raise ApiError(L(
            "Cancel the post first. Only published, failed or cancelled posts can be deleted.",
            "Ακύρωσε πρώτα το post. Διαγράφονται μόνο δημοσιευμένα, αποτυχημένα ή ακυρωμένα.",
        ), 409)
    return jsonify(ok=True)
