"""Facebook Page: posts through the Graph API with a Page access token."""

from __future__ import annotations

import re

import requests

from ..i18n import L
from .base import Field, Image, Platform, PlatformError, PublishResult, error_detail

_PAGE_ID = re.compile(r"^\d{5,30}$")


class FacebookPlatform(Platform):
    key = "facebook"
    label = "Facebook Page"
    max_chars = 63206
    lengths = {"short": 200, "medium": 500, "long": 1200}
    fields = (
        Field("page_id", "Page ID", secret=False, placeholder="104857392018273"),
        Field("page_access_token", "Page Access Token"),
    )

    def __init__(self, graph_version: str = "v26.0", http=None):
        super().__init__(http)
        self.base = f"https://graph.facebook.com/{graph_version}"

    def clean_credentials(self, creds: dict) -> dict:
        creds = super().clean_credentials(creds)
        page_id = creds.get("page_id") or ""
        if page_id and not _PAGE_ID.match(page_id):
            raise PlatformError(L(
                "The Page ID is a number (digits only). See the guide for where to find it.",
                "Το Page ID είναι αριθμός (μόνο ψηφία). Δες τον οδηγό για το πού θα το βρεις.",
            ))
        return creds

    @staticmethod
    def _headers(creds: dict) -> dict:
        # The token goes in a header, never in the URL, so it cannot leak into logs.
        return {"Authorization": f"Bearer {creds['page_access_token']}"}

    def verify(self, creds: dict) -> dict:
        try:
            resp = self.http.get(
                f"{self.base}/{creds['page_id']}", params={"fields": "id,name"},
                headers=self._headers(creds), timeout=20,
            )
        except requests.RequestException as exc:
            raise PlatformError(L("No connection to Facebook. Check the internet.", "Δεν υπάρχει σύνδεση με το Facebook. Έλεγξε το internet.")) from exc
        if resp.status_code != 200:
            raise self._error(resp)
        data = resp.json() or {}
        return {"username": data.get("name"), "page_id": data.get("id")}

    def publish(self, creds: dict, text: str, image: Image | None = None) -> PublishResult:
        page_id = creds["page_id"]
        try:
            if image is not None:
                resp = self.http.post(
                    f"{self.base}/{page_id}/photos",
                    data={"message": text, "published": "true"},
                    files={"source": (image.filename, image.data, image.mime)},
                    headers=self._headers(creds),
                    timeout=90,
                )
            else:
                resp = self.http.post(
                    f"{self.base}/{page_id}/feed", data={"message": text},
                    headers=self._headers(creds), timeout=30,
                )
        except requests.RequestException as exc:
            raise PlatformError(
                L(
                    "Network error while publishing to Facebook. The post may have gone out: "
                    "check the Page before you retry.",
                    "Σφάλμα δικτύου κατά τη δημοσίευση στο Facebook. Το post ίσως δημοσιεύτηκε: "
                    "έλεγξε τη Σελίδα πριν κάνεις retry.",
                ),
                maybe_published=True,
            ) from exc
        if resp.status_code != 200:
            raise self._error(resp)
        data = resp.json() or {}
        post_id = str(data.get("post_id") or data.get("id") or "")
        if not post_id:
            raise PlatformError(L("Facebook returned no id for the post.", "Το Facebook δεν επέστρεψε id για το post."), maybe_published=True)
        return PublishResult(post_id, f"https://www.facebook.com/{post_id}")

    @staticmethod
    def _error(resp: requests.Response) -> PlatformError:
        try:
            code = int(((resp.json() or {}).get("error") or {}).get("code") or 0)
        except (ValueError, TypeError, AttributeError):
            code = 0
        detail = f'{L("Details", "Λεπτομέρειες")}: {error_detail(resp)}'
        if code == 190 or resp.status_code == 401:
            return PlatformError(
                L(
                    f"The Page Access Token is invalid or expired. Get a new token (see the guide). {detail}",
                    f"Το Page Access Token δεν ισχύει ή έληξε. Πάρε νέο token (δες τον οδηγό). {detail}",
                ),
                needs_reconnect=True,
            )
        if code in (10, 200) or 200 <= code < 300:
            msg = L(
                "Permissions are missing. The token needs pages_manage_posts and pages_read_engagement.",
                "Λείπουν permissions. Το token χρειάζεται pages_manage_posts και pages_read_engagement.",
            )
        elif code in (4, 17, 32, 613):
            msg = L("Facebook reached its request limit. Try again later.", "Το Facebook έφτασε το όριο αιτημάτων. Δοκίμασε ξανά αργότερα.")
        elif code == 368:
            msg = L("Facebook has temporarily blocked posting from this Page.", "Το Facebook μπλόκαρε προσωρινά τις δημοσιεύσεις από αυτή τη Σελίδα.")
        elif code == 803 or code == 100:
            msg = L(
                "Facebook could not find the Page or did not accept the details. Check the Page ID.",
                "Το Facebook δεν βρήκε τη Σελίδα ή δεν δέχτηκε τα στοιχεία. Έλεγξε το Page ID.",
            )
        else:
            msg = L(f"Facebook error ({resp.status_code}).", f"Σφάλμα Facebook ({resp.status_code}).")
        return PlatformError(f"{msg} {detail}")
