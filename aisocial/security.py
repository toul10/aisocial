"""Request guards: Host allow-list, CSRF header, optional password, security headers.

The app has no user accounts: it is meant to run on your own computer. These
guards stop other websites in your browser (CSRF, DNS rebinding) and other
devices on the network from using it.
"""

from __future__ import annotations

import hmac
from urllib.parse import urlparse

from flask import Response, jsonify, request

from .i18n import L

CSRF_HEADER = "X-AISocial-Request"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CSP = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; "
    "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)


def _password_ok(expected: str) -> bool:
    auth = request.authorization
    if auth is None or auth.type != "basic":
        return False
    return hmac.compare_digest((auth.password or "").encode(), expected.encode())


def init_app(app, settings) -> None:
    @app.before_request
    def _guard():
        host = (request.host or "").lower()
        if host not in settings.allowed_hosts:
            return Response(
                f"Host not allowed. Open the app at {settings.public_url}",
                status=400, mimetype="text/plain",
            )
        if settings.password and request.path != "/healthz" and not _password_ok(settings.password):
            return Response(
                "Login required", status=401,
                headers={"WWW-Authenticate": 'Basic realm="AI Social", charset="UTF-8"'},
            )
        if request.method not in SAFE_METHODS:
            # Custom headers cannot be sent cross-site without a CORS preflight,
            # which this app never approves.
            if request.headers.get(CSRF_HEADER) != "1":
                return jsonify(ok=False, error=L("Invalid request (the CSRF header is missing).", "Μη έγκυρο αίτημα (λείπει το CSRF header).")), 403
            origin = request.headers.get("Origin")
            if origin is not None and (urlparse(origin).netloc or "").lower() not in settings.allowed_hosts:
                return jsonify(ok=False, error=L("Origin not allowed.", "Μη επιτρεπτό origin.")), 403
        return None

    @app.after_request
    def _headers(resp):
        resp.headers.setdefault("Content-Security-Policy", CSP)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if request.path.startswith("/api/"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp
