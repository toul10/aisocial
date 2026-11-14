"""Publishes a post row to its platform and records the outcome."""

from __future__ import annotations

import logging

from . import db, media
from .crypto import DecryptionError
from .i18n import L
from .platforms import PlatformError, redact

log = logging.getLogger(__name__)


class Publisher:
    def __init__(self, settings, box, platforms: dict):
        self.settings = settings
        self.box = box
        self.platforms = platforms

    def publish(self, conn, post_id: int, *, from_statuses: tuple[str, ...] = ("scheduled",)) -> dict | None:
        """Claim the post atomically, then publish it. Safe against double posting."""
        if not db.claim_post(conn, post_id, from_statuses):
            return db.get_post(conn, post_id)
        return self.run_claimed(conn, post_id)

    def run_claimed(self, conn, post_id: int) -> dict | None:
        """Publish a post that is already in 'publishing' state."""
        post = db.get_post(conn, post_id)
        account = None
        creds: dict = {}
        try:
            account = db.get_account(conn, post["account_id"]) if post["account_id"] else None
            if account is None:
                raise PlatformError(L("The account of this post no longer exists.", "Ο λογαριασμός αυτού του post δεν υπάρχει πια."))
            platform = self.platforms.get(account["platform"])
            if platform is None:
                raise PlatformError(L(f"Unknown platform: {account['platform']}", f"Άγνωστη πλατφόρμα: {account['platform']}"))
            creds = self.box.decrypt_json(account["credentials_enc"])
            count = platform.count(post["text"])
            if count > platform.max_chars:
                raise PlatformError(L(
                    f"The text has {count} characters; {platform.label} allows up to {platform.max_chars}.",
                    f"Το κείμενο έχει {count} χαρακτήρες, ενώ το {platform.label} επιτρέπει έως {platform.max_chars}.",
                ))
            image = media.load_image(self.settings.media_dir, post["image_id"]) if post["image_id"] else None
            result = platform.publish(creds, post["text"], image)
        except PlatformError as exc:
            message = redact(str(exc), creds.values())
            db.finish_post(conn, post_id, status="failed", error=message)
            if exc.needs_reconnect and account is not None:
                status = dict(account["status"], ok=False, error=message, checked_at=db.now())
                db.update_account(conn, account["id"], status=status)
        except (DecryptionError, media.MediaError) as exc:
            db.finish_post(conn, post_id, status="failed", error=str(exc))
        except Exception as exc:  # never leave a row stuck in 'publishing'
            log.exception("Unexpected error while publishing post %s", post_id)
            prefix = L("Unexpected error", "Απρόσμενο σφάλμα")
            message = redact(f"{prefix}: {exc.__class__.__name__}: {exc}", creds.values())
            db.finish_post(conn, post_id, status="failed", error=message)
        else:
            db.finish_post(conn, post_id, status="published",
                           external_id=result.external_id, external_url=result.url)
        return db.get_post(conn, post_id)
