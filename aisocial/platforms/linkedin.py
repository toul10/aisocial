"""LinkedIn: posts on a personal profile, via OAuth 2.0 ("Share on LinkedIn")."""

from __future__ import annotations

import re
import time
from datetime import date
from urllib.parse import urlencode, urlparse

import requests

from ..i18n import L
from .base import Field, Image, Platform, PlatformError, PublishResult, error_detail

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
API = "https://api.linkedin.com"
SCOPES = "openid profile w_member_social"

# Reserved characters of LinkedIn's "little" text format. Unescaped, some of them
# silently truncate the post (for example "(").
_RESERVED = set("\\|{}@[]()<>#*_~")
_HASHTAG = re.compile(r"(?<![\w&])#([^\W_]+)")


def _escape(segment: str) -> str:
    return "".join("\\" + ch if ch in _RESERVED else ch for ch in segment)


def to_little_text(text: str) -> str:
    """Escape plain text for the Posts API commentary, keeping #hashtags clickable."""
    out, pos = [], 0
    for match in _HASHTAG.finditer(text):
        out.append(_escape(text[pos:match.start()]))
        out.append("#" + match.group(1))
        pos = match.end()
    out.append(_escape(text[pos:]))
    return "".join(out)


def recent_versions(today: date | None = None, count: int = 6) -> list[str]:
    """LinkedIn API versions (YYYYMM) to try, newest first, starting last month.

    Versions are released most months and retired after about a year, so a
    recent one is used instead of a hard-coded value that would expire.
    """
    d = today or date.today()
    year, month = d.year, d.month
    versions = []
    for _ in range(count):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        versions.append(f"{year}{month:02d}")
    return versions


class LinkedInPlatform(Platform):
    key = "linkedin"
    label = "LinkedIn"
    max_chars = 3000
    lengths = {"short": 400, "medium": 900, "long": 1800}
    oauth = True
    fields = (
        Field("client_id", "Client ID", secret=False),
        Field("client_secret", "Primary Client Secret"),
    )

    def __init__(self, api_version: str = "", http=None):
        super().__init__(http)
        self._pinned_version = api_version.strip()
        self._working_version: str | None = None

    # --- OAuth ------------------------------------------------------------------

    def authorize_url(self, creds: dict, redirect_uri: str, state: str) -> str:
        query = urlencode({
            "response_type": "code",
            "client_id": creds["client_id"],
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": SCOPES,
        })
        return f"{AUTH_URL}?{query}"

    def exchange_code(self, creds: dict, code: str, redirect_uri: str) -> dict:
        try:
            resp = self.http.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": creds["client_id"],
                    "client_secret": creds["client_secret"],
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            raise PlatformError(L("Network error while connecting to LinkedIn.", "Σφάλμα δικτύου κατά τη σύνδεση με το LinkedIn.")) from exc
        if resp.status_code != 200:
            raise PlatformError(L(
                f"LinkedIn did not grant access ({resp.status_code}): {error_detail(resp)}. "
                "Check the Client ID/Secret and that the app's Redirect URL is exactly the same.",
                f"Το LinkedIn δεν έδωσε πρόσβαση ({resp.status_code}): {error_detail(resp)}. "
                "Έλεγξε Client ID/Secret και ότι το Redirect URL στο app είναι ακριβώς ίδιο.",
            ))
        token = resp.json() or {}
        access_token = token.get("access_token")
        if not access_token:
            raise PlatformError(L("LinkedIn returned no access token.", "Το LinkedIn δεν επέστρεψε access token."))
        info = self._userinfo(access_token)
        updated = dict(creds)
        updated.update({
            "access_token": access_token,
            "expires_at": time.time() + int(token.get("expires_in") or 0),
            "person_urn": f"urn:li:person:{info['sub']}",
            "member_name": info.get("name") or "",
        })
        if token.get("refresh_token"):
            updated["refresh_token"] = token["refresh_token"]
        return updated

    def _userinfo(self, access_token: str) -> dict:
        try:
            resp = self.http.get(
                f"{API}/v2/userinfo", headers={"Authorization": f"Bearer {access_token}"}, timeout=20
            )
        except requests.RequestException as exc:
            raise PlatformError(L("No connection to LinkedIn. Check the internet.", "Δεν υπάρχει σύνδεση με το LinkedIn. Έλεγξε το internet.")) from exc
        if resp.status_code == 401:
            raise PlatformError(
                L(
                    "The LinkedIn connection is no longer valid. Connect LinkedIn again (Settings → Accounts).",
                    "Η σύνδεση LinkedIn δεν ισχύει πλέον. Σύνδεσε ξανά το LinkedIn (Ρυθμίσεις → Λογαριασμοί).",
                ),
                needs_reconnect=True,
            )
        if resp.status_code != 200:
            raise PlatformError(L(
                f"LinkedIn error ({resp.status_code}): {error_detail(resp)}. Make sure the app "
                "has the product “Sign In with LinkedIn using OpenID Connect”.",
                f"Σφάλμα LinkedIn ({resp.status_code}): {error_detail(resp)}. Βεβαιώσου ότι το app "
                "έχει το product «Sign In with LinkedIn using OpenID Connect».",
            ))
        data = resp.json() or {}
        if not data.get("sub"):
            raise PlatformError(L("LinkedIn returned no member id.", "Το LinkedIn δεν επέστρεψε member id."))
        return data

    def _token(self, creds: dict) -> str:
        token = creds.get("access_token")
        if not token:
            raise PlatformError(
                L(
                    "The LinkedIn account is not connected yet. Press “Connect LinkedIn”.",
                    "Ο λογαριασμός LinkedIn δεν έχει συνδεθεί ακόμα. Πάτα «Σύνδεση LinkedIn».",
                ),
                needs_reconnect=True,
            )
        expires_at = float(creds.get("expires_at") or 0)
        if expires_at and expires_at < time.time() + 60:
            raise PlatformError(
                L(
                    "The LinkedIn connection expired (it lasts 60 days). Press “Reconnect” (Settings → Accounts).",
                    "Η σύνδεση LinkedIn έληξε (ισχύει 60 μέρες). Πάτα «Επανασύνδεση» (Ρυθμίσεις → Λογαριασμοί).",
                ),
                needs_reconnect=True,
            )
        return token

    # --- API --------------------------------------------------------------------

    def verify(self, creds: dict) -> dict:
        info = self._userinfo(self._token(creds))
        return {"username": info.get("name") or creds.get("member_name"), "expires_at": creds.get("expires_at")}

    def publish(self, creds: dict, text: str, image: Image | None = None) -> PublishResult:
        token = self._token(creds)
        author = creds.get("person_urn")
        if not author:
            raise PlatformError(
                L(
                    "The LinkedIn member id is missing. Press “Reconnect” (Settings → Accounts).",
                    "Λείπει το LinkedIn member id. Πάτα «Επανασύνδεση» (Ρυθμίσεις → Λογαριασμοί).",
                ),
                needs_reconnect=True,
            )
        body: dict = {
            "author": author,
            "commentary": to_little_text(text),
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if image is not None:
            body["content"] = {"media": {"id": self._upload_image(token, author, image)}}
        resp = self._rest("POST", "/rest/posts", token, json=body, final=True)
        if resp.status_code != 201:
            raise self._error(resp, L("publishing", "τη δημοσίευση"))
        urn = resp.headers.get("x-restli-id") or resp.headers.get("x-linkedin-id") or ""
        return PublishResult(urn, f"https://www.linkedin.com/feed/update/{urn}/" if urn else None)

    def _upload_image(self, token: str, owner: str, image: Image) -> str:
        resp = self._rest(
            "POST", "/rest/images?action=initializeUpload", token,
            json={"initializeUploadRequest": {"owner": owner}},
        )
        if resp.status_code != 200:
            raise self._error(resp, L("the image upload", "το upload της εικόνας"))
        value = (resp.json() or {}).get("value") or {}
        upload_url, image_urn = value.get("uploadUrl"), value.get("image")
        if not upload_url or not image_urn:
            raise PlatformError(L("LinkedIn returned no upload address for the image.", "Το LinkedIn δεν επέστρεψε διεύθυνση upload για την εικόνα."))
        headers = {"Content-Type": image.mime}
        host = (urlparse(upload_url).hostname or "").lower()
        if host == "linkedin.com" or host.endswith(".linkedin.com"):
            headers["Authorization"] = f"Bearer {token}"
        try:
            up = self.http.put(upload_url, data=image.data, headers=headers, timeout=90)
        except requests.RequestException as exc:
            raise PlatformError(L("Network error while uploading the image to LinkedIn.", "Σφάλμα δικτύου κατά το upload της εικόνας στο LinkedIn.")) from exc
        if up.status_code not in (200, 201):
            raise PlatformError(L(f"The image upload to LinkedIn failed ({up.status_code}).", f"Το upload της εικόνας στο LinkedIn απέτυχε ({up.status_code})."))
        return image_urn

    def _versions(self) -> list[str]:
        if self._pinned_version:
            return [self._pinned_version]
        candidates = recent_versions()
        if self._working_version and self._working_version in candidates:
            candidates.remove(self._working_version)
            candidates.insert(0, self._working_version)
        return candidates

    @staticmethod
    def _is_version_error(resp: requests.Response) -> bool:
        return resp.status_code == 426 or (resp.status_code == 400 and "version" in error_detail(resp).lower())

    def _rest(self, method: str, path: str, token: str, *, json: dict, final: bool = False) -> requests.Response:
        last = None
        versions = self._versions()
        for version in versions:
            headers = {
                "Authorization": f"Bearer {token}",
                "LinkedIn-Version": version,
                "X-Restli-Protocol-Version": "2.0.0",
            }
            try:
                resp = self.http.request(method, f"{API}{path}", headers=headers, json=json, timeout=30)
            except requests.RequestException as exc:
                if final:
                    raise PlatformError(
                        L(
                            "Network error while publishing to LinkedIn. The post may have "
                            "gone out: check LinkedIn before you retry.",
                            "Σφάλμα δικτύου κατά τη δημοσίευση στο LinkedIn. Το post ίσως "
                            "δημοσιεύτηκε: έλεγξε το LinkedIn πριν κάνεις retry.",
                        ),
                        maybe_published=True,
                    ) from exc
                raise PlatformError(L("Network error with LinkedIn.", "Σφάλμα δικτύου με το LinkedIn.")) from exc
            if self._is_version_error(resp):
                last = resp
                continue
            if not self._pinned_version:
                self._working_version = version
            return resp
        raise PlatformError(L(
            f"LinkedIn accepted none of the API versions ({', '.join(versions)}). Set "
            f"LINKEDIN_API_VERSION in .env. Details: {error_detail(last)}",
            f"Το LinkedIn δεν δέχτηκε καμία API version ({', '.join(versions)}). Όρισε "
            f"LINKEDIN_API_VERSION στο .env. Λεπτομέρειες: {error_detail(last)}",
        ))

    def _error(self, resp: requests.Response, action: str) -> PlatformError:
        status = resp.status_code
        if status == 401:
            return PlatformError(
                L(
                    "The LinkedIn connection is no longer valid (401). Press “Reconnect” (Settings → Accounts).",
                    "Η σύνδεση LinkedIn δεν ισχύει πλέον (401). Πάτα «Επανασύνδεση» (Ρυθμίσεις → Λογαριασμοί).",
                ),
                needs_reconnect=True,
            )
        if status == 403:
            msg = L(
                "LinkedIn refused the request (403). Make sure the app has the product "
                "“Share on LinkedIn”. If you added it after connecting, press “Reconnect” (Settings → Accounts).",
                "Το LinkedIn αρνήθηκε το αίτημα (403). Βεβαιώσου ότι το app έχει το product "
                "«Share on LinkedIn». Αν το πρόσθεσες μετά τη σύνδεση, πάτα «Επανασύνδεση» (Ρυθμίσεις → Λογαριασμοί).",
            )
        elif status == 422:
            msg = L(
                "LinkedIn rejected the content (422), for example because it matches an earlier post.",
                "Το LinkedIn απέρριψε το περιεχόμενο (422), π.χ. επειδή είναι ίδιο με παλιότερο post.",
            )
        elif status == 429:
            msg = L("LinkedIn reached its request limit (429). Try again later.", "Το LinkedIn έφτασε το όριο αιτημάτων (429). Δοκίμασε ξανά αργότερα.")
        else:
            msg = L(f"LinkedIn error ({status}) during {action}.", f"Σφάλμα LinkedIn ({status}) κατά {action}.")
        details = L("Details", "Λεπτομέρειες")
        return PlatformError(f"{msg} {details}: {error_detail(resp)}")
