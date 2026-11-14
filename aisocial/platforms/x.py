"""X (Twitter): API v2 with OAuth 1.0a user-context keys from the developer portal."""

from __future__ import annotations

import re
import unicodedata

import requests
from requests_oauthlib import OAuth1

from ..i18n import L
from .base import Field, Image, Platform, PlatformError, PublishResult, error_detail

API = "https://api.x.com/2"
_URL = re.compile(r"https?://\S+", re.IGNORECASE)


def _weigh(segment: str) -> int:
    total = 0
    for ch in segment:
        cp = ord(ch)
        light = cp <= 0x10FF or 0x2000 <= cp <= 0x200D or 0x2010 <= cp <= 0x201F or 0x2032 <= cp <= 0x2037
        total += 1 if light else 2
    return total


def weighted_length(text: str) -> int:
    """Approximate X's weighted length (twitter-text v3 rules).

    Latin, Greek and Cyrillic characters count 1; emoji, CJK and other
    characters count 2; every http(s) URL counts 23. Errs on the high side.
    """
    text = unicodedata.normalize("NFC", text)
    total, pos = 0, 0
    for match in _URL.finditer(text):
        total += _weigh(text[pos:match.start()]) + 23
        pos = match.end()
    return total + _weigh(text[pos:])


class XPlatform(Platform):
    key = "x"
    label = "X (Twitter)"
    max_chars = 280
    lengths = {"short": 140, "medium": 220, "long": 270}
    fields = (
        Field("api_key", "API Key (Consumer Key)"),
        Field("api_secret", "API Key Secret (Consumer Secret)"),
        Field("access_token", "Access Token"),
        Field("access_token_secret", "Access Token Secret"),
    )

    def count(self, text: str) -> int:
        return weighted_length(text)

    def clean_credentials(self, creds: dict) -> dict:
        creds = super().clean_credentials(creds)
        for field in self.fields:
            value = creds.get(field.name) or ""
            if any(ch.isspace() for ch in value):
                raise PlatformError(L(
                    f"“{field.label}” must not contain spaces. Copy it again.",
                    f"Το «{field.label}» δεν πρέπει να έχει κενά. Αντέγραψέ το ξανά.",
                ))
        return creds

    def _auth(self, creds: dict) -> OAuth1:
        return OAuth1(creds["api_key"], creds["api_secret"], creds["access_token"], creds["access_token_secret"])

    def verify(self, creds: dict) -> dict:
        try:
            resp = self.http.get(f"{API}/users/me", auth=self._auth(creds), timeout=20)
        except requests.RequestException as exc:
            raise PlatformError(L("No connection to X. Check the internet.", "Δεν υπάρχει σύνδεση με το X. Έλεγξε το internet.")) from exc
        if resp.status_code != 200:
            raise self._error(resp, L("the account check", "τον έλεγχο του λογαριασμού"))
        data = (resp.json() or {}).get("data") or {}
        username = data.get("username")
        return {"username": f"@{username}" if username else None, "display_name": data.get("name")}

    def publish(self, creds: dict, text: str, image: Image | None = None) -> PublishResult:
        body: dict = {"text": text}
        if image is not None:
            body["media"] = {"media_ids": [self._upload(creds, image)]}
        try:
            resp = self.http.post(f"{API}/tweets", json=body, auth=self._auth(creds), timeout=30)
        except requests.RequestException as exc:
            raise PlatformError(
                L(
                    "Network error while publishing to X. The post may have gone out: "
                    "check X before you retry.",
                    "Σφάλμα δικτύου κατά τη δημοσίευση στο X. Το post ίσως δημοσιεύτηκε: "
                    "έλεγξε το X πριν κάνεις retry.",
                ),
                maybe_published=True,
            ) from exc
        if resp.status_code not in (200, 201):
            raise self._error(resp, L("publishing", "τη δημοσίευση"))
        tweet_id = str(((resp.json() or {}).get("data") or {}).get("id") or "")
        if not tweet_id:
            raise PlatformError(L("X returned no id for the post.", "Το X δεν επέστρεψε id για το post."), maybe_published=True)
        return PublishResult(tweet_id, f"https://x.com/i/web/status/{tweet_id}")

    def _upload(self, creds: dict, image: Image) -> str:
        category = "tweet_gif" if image.mime == "image/gif" else "tweet_image"
        try:
            resp = self.http.post(
                f"{API}/media/upload",
                files={"media": (image.filename, image.data, image.mime)},
                data={"media_category": category, "media_type": image.mime},
                auth=self._auth(creds),
                timeout=90,
            )
        except requests.RequestException as exc:
            raise PlatformError(L("Network error while uploading the image to X.", "Σφάλμα δικτύου κατά το upload της εικόνας στο X.")) from exc
        if resp.status_code not in (200, 201):
            raise self._error(resp, L("the image upload", "το upload της εικόνας"))
        payload = resp.json() or {}
        media_id = (payload.get("data") or {}).get("id") or payload.get("media_id_string")
        if not media_id:
            raise PlatformError(L("X returned no media id for the image.", "Το X δεν επέστρεψε media id για την εικόνα."))
        return str(media_id)

    def _error(self, resp: requests.Response, action: str) -> PlatformError:
        status = resp.status_code
        if status == 401:
            msg = L(
                "X rejected the keys (401). Check that all 4 keys were copied correctly.",
                "Το X απέρριψε τα keys (401). Έλεγξε ότι αντέγραψες σωστά και τα 4 keys.",
            )
        elif status == 402:
            msg = L(
                "X asks for payment (402): the developer account has no credits or plan for posting.",
                "Το X ζητά πληρωμή (402): ο developer λογαριασμός δεν έχει credits ή πλάνο για posting.",
            )
        elif status == 403:
            msg = L(
                "X refused the request (403). Common causes: the app lacks “Read and write” "
                "permission (after changing it, create the Access Token again), there are no credits, "
                "or the same text was already published.",
                "Το X αρνήθηκε το αίτημα (403). Συνήθεις αιτίες: το app δεν έχει «Read and write» "
                "permission (μετά την αλλαγή ξαναφτιάξε το Access Token), δεν υπάρχουν credits, "
                "ή το ίδιο κείμενο δημοσιεύτηκε ήδη.",
            )
        elif status == 429:
            msg = L("X reached its request limit (429). Try again later.", "Το X έφτασε το όριο αιτημάτων (429). Δοκίμασε ξανά αργότερα.")
        else:
            msg = L(f"X error ({status}) during {action}.", f"Σφάλμα X ({status}) κατά {action}.")
        details = L("Details", "Λεπτομέρειες")
        return PlatformError(f"{msg} {details}: {error_detail(resp)}", needs_reconnect=status == 401)
