"""Interface language: English (the default) or Greek, one choice for the whole app.

Every text the user sees is written in both languages right where it is used:

    raise ApiError(L("Choose a time.", "Διάλεξε ώρα."))

The choice is saved in the database (meta key "ui_language") and mirrored here, so texts made
outside a web request (the scheduler, the start-up recovery) follow it too. Text that was already
saved, such as a post's error message, stays in the language it was written in.
"""

from __future__ import annotations

LANGUAGES = ("en", "el")
DEFAULT_LANGUAGE = "en"
META_KEY = "ui_language"

_current = DEFAULT_LANGUAGE


def set_language(value: str | None) -> str:
    """Switch the language for the whole process. Anything unknown falls back to English."""
    global _current
    _current = value if value in LANGUAGES else DEFAULT_LANGUAGE
    return _current


def language() -> str:
    return _current


def L(en: str, el: str) -> str:  # noqa: N802 (short on purpose: it wraps every visible text)
    """The text in the current language."""
    return el if _current == "el" else en


def plural(count: int, en_one: str, en_many: str, el_one: str, el_many: str) -> str:
    """'1 post' / '3 posts'. Both languages use the singular only for exactly one."""
    return L(en_one if count == 1 else en_many, el_one if count == 1 else el_many).format(n=count)
