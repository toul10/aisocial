"""HTML pages (the UI itself is rendered by the JavaScript in static/js)."""

from __future__ import annotations

from flask import Blueprint, abort, redirect, render_template, send_file, url_for

from .. import db, media
from . import get_db, services

bp = Blueprint("pages", __name__)


def _setup_completed() -> bool:
    return db.get_meta(get_db(), "setup_completed") == "1"


@bp.get("/")
def dashboard():
    if not _setup_completed():
        return redirect(url_for("pages.setup"))
    return render_template("dashboard.html", page="dashboard")


@bp.get("/new")
def compose():
    return render_template("compose.html", page="compose")


@bp.get("/posts")
def posts():
    return render_template("posts.html", page="posts")


@bp.get("/settings")
def settings():
    return render_template("settings.html", page="settings")


@bp.get("/setup")
def setup():
    return render_template("setup.html", page="setup")


@bp.get("/media/<image_id>")
def media_file(image_id: str):
    path = media.image_path(services().settings.media_dir, image_id)
    if path is None:
        abort(404)
    return send_file(path, mimetype=media.mime_for(image_id), max_age=86400)


@bp.get("/healthz")
def healthz():
    return "aisocial ok", 200, {"Content-Type": "text/plain"}
