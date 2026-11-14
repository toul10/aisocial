"""AI Social: AI-written posts for X, LinkedIn and Facebook, published now or on a schedule."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from flask import Flask, jsonify, request

from . import db, i18n, security
from .ai import AIService
from .config import PROJECT_ROOT, Settings
from .crypto import DecryptionError, SecretBox
from .platforms import Platform, build_platforms
from .publisher import Publisher
from .scheduler import Scheduler

__version__ = "1.1.0"

log = logging.getLogger(__name__)


@dataclass
class Services:
    settings: Settings
    box: SecretBox
    ai: AIService
    platforms: dict[str, Platform]
    publisher: Publisher
    scheduler: Scheduler


def create_app(settings: Settings | None = None, *, platforms: dict[str, Platform] | None = None,
               start_scheduler: bool = True) -> Flask:
    """Build the Flask app. Tests pass their own settings/platforms and start_scheduler=False."""
    if settings is None:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
        settings = Settings.from_env()

    db.init_db(settings.db_path)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    box = SecretBox(settings.app_secret)

    def stored_key(name: str) -> str:
        with db.open_db(settings.db_path) as conn:
            value = db.get_secret(conn, name)
        if value is None:
            return ""
        try:
            return box.decrypt_text(value)
        except DecryptionError:
            log.warning("The saved %s cannot be decrypted (APP_SECRET changed?). Enter it again.", name)
            return ""

    def stored_provider() -> str:
        with db.open_db(settings.db_path) as conn:
            return db.get_meta(conn, "ai_text_provider")

    ai = AIService(settings, stored_key=stored_key, stored_provider=stored_provider)
    platforms = platforms if platforms is not None else build_platforms(settings)
    publisher = Publisher(settings, box, platforms)
    with db.open_db(settings.db_path) as conn:
        i18n.set_language(db.get_meta(conn, i18n.META_KEY))  # before any message is written
        recovered = db.recover_interrupted(conn)
    if recovered:
        log.warning("%s post(s) were interrupted while publishing; marked as failed.", recovered)
    scheduler = Scheduler(settings, publisher)

    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=8 * 1024 * 1024, SEND_FILE_MAX_AGE_DEFAULT=0)
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    app.extensions["aisocial"] = Services(settings, box, ai, platforms, publisher, scheduler)

    security.init_app(app, settings)
    from .web import register_blueprints

    register_blueprints(app)

    @app.context_processor
    def _template_globals():
        return {"asset_version": __version__, "lang": i18n.language(), "L": i18n.L}

    def _json_error(exc, status: int, message: str):
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error=message), status
        return exc

    @app.errorhandler(404)
    def _not_found(exc):
        return _json_error(exc, 404, i18n.L("Not found.", "Δεν βρέθηκε."))

    @app.errorhandler(405)
    def _bad_method(exc):
        return _json_error(exc, 405, i18n.L("Method not allowed.", "Μη επιτρεπτή μέθοδος."))

    @app.errorhandler(413)
    def _too_large(exc):
        return _json_error(exc, 413, i18n.L("The file is too large (up to 5 MB).", "Το αρχείο είναι πολύ μεγάλο (έως 5 MB)."))

    @app.errorhandler(500)
    def _server_error(exc):
        return _json_error(exc, 500, i18n.L(
            "Unexpected error. See the AI Social window for details.",
            "Απρόσμενο σφάλμα. Δες το παράθυρο του AI Social για λεπτομέρειες.",
        ))

    if start_scheduler:
        scheduler.start()
    return app
