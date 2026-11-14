"""LinkedIn OAuth 2.0: /oauth/linkedin/start/<id> → LinkedIn → /oauth/linkedin/callback.

The state value is stored in the database (not a cookie), so the flow works even
if LinkedIn sends the browser back to localhost while the app was opened as
127.0.0.1.
"""

from __future__ import annotations

import secrets

from flask import Blueprint, redirect, request, url_for

from .. import db
from ..crypto import DecryptionError
from ..i18n import L
from ..platforms import PlatformError, redact
from . import get_db, services

bp = Blueprint("oauth", __name__, url_prefix="/oauth")

RETURN_PAGES = {"settings": "pages.settings", "setup": "pages.setup"}


def _back(return_to: str, *, error: str | None = None):
    endpoint = RETURN_PAGES.get(return_to, "pages.settings")
    params = {"linkedin_error": error[:400]} if error else {"linkedin": "connected"}
    return redirect(url_for(endpoint, _anchor="accounts", **params))


@bp.get("/linkedin/start/<int:account_id>")
def linkedin_start(account_id: int):
    s = services()
    conn = get_db()
    return_to = request.args.get("return", "settings")
    if return_to not in RETURN_PAGES:
        return_to = "settings"
    account = db.get_account(conn, account_id)
    platform = s.platforms.get("linkedin")
    if account is None or platform is None or account["platform"] != "linkedin":
        return _back(return_to, error=L("LinkedIn account not found.", "Ο λογαριασμός LinkedIn δεν βρέθηκε."))
    try:
        creds = s.box.decrypt_json(account["credentials_enc"])
    except DecryptionError as exc:
        return _back(return_to, error=str(exc))
    if not creds.get("client_id") or not creds.get("client_secret"):
        return _back(return_to, error=L("Fill in the Client ID and Client Secret first.", "Συμπλήρωσε πρώτα Client ID και Client Secret."))
    state = secrets.token_urlsafe(32)
    db.save_oauth_state(conn, state, account_id, return_to)
    return redirect(platform.authorize_url(creds, s.settings.linkedin_redirect_uri, state))


@bp.get("/linkedin/callback")
def linkedin_callback():
    s = services()
    conn = get_db()
    state = request.args.get("state") or ""
    popped = db.pop_oauth_state(conn, state) if state else None
    if popped is None:
        return _back("settings", error=L(
            "The LinkedIn connection did not finish (it took over 10 minutes or the link "
            "was already used). Press “Connect LinkedIn” again.",
            "Η σύνδεση LinkedIn δεν ολοκληρώθηκε (άργησε πάνω από 10 λεπτά ή ο σύνδεσμος "
            "χρησιμοποιήθηκε ήδη). Πάτα «Σύνδεση LinkedIn» ξανά.",
        ))
    account_id, return_to = popped
    if request.args.get("error"):
        reason = request.args.get("error_description") or request.args.get("error")
        return _back(return_to, error=L(f"LinkedIn did not give permission: {reason}", f"Το LinkedIn δεν έδωσε άδεια: {reason}"))
    code = request.args.get("code") or ""
    account = db.get_account(conn, account_id)
    platform = s.platforms.get("linkedin")
    if not code or account is None or platform is None:
        return _back(return_to, error=L("The LinkedIn connection failed. Try again.", "Η σύνδεση LinkedIn απέτυχε. Δοκίμασε ξανά."))
    creds: dict = {}
    try:
        creds = s.box.decrypt_json(account["credentials_enc"])
        updated = platform.exchange_code(creds, code, s.settings.linkedin_redirect_uri)
    except DecryptionError as exc:
        return _back(return_to, error=str(exc))
    except PlatformError as exc:
        return _back(return_to, error=redact(str(exc), [*creds.values(), code]))
    status = {"ok": True, "error": None, "checked_at": db.now(), "username": updated.get("member_name") or None}
    db.update_account(conn, account_id, credentials_enc=s.box.encrypt_json(updated), status=status)
    return _back(return_to)
