"""Background thread that publishes scheduled posts when they are due."""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from . import db
from .i18n import L

log = logging.getLogger(__name__)


def missed_message(scheduled_at: float) -> str:
    when = datetime.fromtimestamp(scheduled_at).strftime("%d/%m/%Y %H:%M")
    return L(
        f"Not published: AI Social was not running at the scheduled time ({when}). "
        "Press “Publish now” or schedule it again.",
        f"Δεν δημοσιεύτηκε: το πρόγραμμα δεν έτρεχε την ώρα που είχε οριστεί ({when}). "
        "Πάτα «Δημοσίευση τώρα» ή φτιάξε νέο προγραμματισμό.",
    )


class Scheduler:
    def __init__(self, settings, publisher):
        self.settings = settings
        self.publisher = publisher
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="aisocial-scheduler", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def tick(self, at: float | None = None) -> int:
        """Publish every due post once. Returns how many posts were handled."""
        at = db.now() if at is None else at
        handled = 0
        with db.open_db(self.settings.db_path) as conn:
            for post in db.due_posts(conn, at):
                if self._stop.is_set():
                    break
                scheduled_at = post["scheduled_at"] or at
                if at - scheduled_at > self.settings.max_late_minutes * 60:
                    if db.set_post_status(conn, post["id"], "failed", ("scheduled",),
                                          error=missed_message(scheduled_at)):
                        handled += 1
                    continue
                self.publisher.publish(conn, post["id"])
                handled += 1
        return handled

    def _run(self) -> None:
        log.info("Scheduler started (every %ss)", self.settings.scheduler_interval)
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:  # keep the loop alive; the error is logged
                log.exception("Scheduler tick failed")
            self._stop.wait(self.settings.scheduler_interval)
