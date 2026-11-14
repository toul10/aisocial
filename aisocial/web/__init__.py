"""HTTP layer: HTML pages, JSON API and OAuth callbacks."""

from __future__ import annotations

from flask import current_app, g

from .. import db


def services():
    return current_app.extensions["aisocial"]


def get_db():
    """One SQLite connection per request, closed on teardown."""
    if "db" not in g:
        g.db = db.connect(services().settings.db_path)
    return g.db


def register_blueprints(app) -> None:
    from .api import bp as api_bp
    from .oauth import bp as oauth_bp
    from .pages import bp as pages_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(oauth_bp)

    @app.teardown_appcontext
    def _close_db(_exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()
