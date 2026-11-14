"""Image storage for post attachments (uploaded or AI-generated)."""

from __future__ import annotations

import re
import secrets
from pathlib import Path

from .i18n import L
from .platforms.base import Image

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # X's limit for images; fine for LinkedIn and Facebook
IMAGE_ID_RE = re.compile(r"^[0-9a-f]{32}\.(png|jpg|gif)$")
_MIME = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif"}


class MediaError(ValueError):
    """The image is missing, too big or not a supported format."""


def sniff(data: bytes) -> str:
    """Return the file extension for supported image bytes, or raise MediaError."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    raise MediaError(L("Only PNG, JPEG or GIF images are supported.", "Υποστηρίζονται μόνο εικόνες PNG, JPEG ή GIF."))


def save_image(media_dir: Path, data: bytes) -> str:
    if not data:
        raise MediaError(L("The file is empty.", "Το αρχείο είναι κενό."))
    if len(data) > MAX_IMAGE_BYTES:
        raise MediaError(L("The image is over 5 MB. Choose a smaller one.", "Η εικόνα είναι πάνω από 5 MB. Διάλεξε μικρότερη."))
    ext = sniff(data)
    media_dir.mkdir(parents=True, exist_ok=True)
    image_id = f"{secrets.token_hex(16)}.{ext}"
    (media_dir / image_id).write_bytes(data)
    return image_id


def image_path(media_dir: Path, image_id: str) -> Path | None:
    if not IMAGE_ID_RE.match(image_id or ""):
        return None
    path = media_dir / image_id
    return path if path.is_file() else None


def load_image(media_dir: Path, image_id: str) -> Image:
    path = image_path(media_dir, image_id)
    if path is None:
        raise MediaError(L("The post's image was not found (it may have been deleted).", "Η εικόνα του post δεν βρέθηκε (ίσως διαγράφηκε)."))
    ext = image_id.rsplit(".", 1)[1]
    return Image(data=path.read_bytes(), mime=_MIME[ext], filename=f"image.{ext}")


def mime_for(image_id: str) -> str:
    return _MIME[image_id.rsplit(".", 1)[1]]
