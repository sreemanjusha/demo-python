import os
import time
from typing import Any
import httpx

BASE = "https://www.linkedin.com"
PROFILE_PATH = "/voyager/api/identity/dash/profiles"

class LinkedInAuthError(Exception): pass
class LinkedInRateLimitError(Exception): pass
class LinkedInUpstreamError(Exception): pass

class LinkedInClient:
    def __init__(self, li_at: str, jsessionid: str, query_decoration: str | None = None,
                 timeout: float = 20.0):
        self.li_at = li_at.strip()
        self.jsessionid = jsessionid.strip()
        self.query_decoration = query_decoration or os.getenv(
            "LINKEDIN_PROFILE_DECORATION",
            "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-101",
        )
        self.timeout = timeout
        if not self.li_at or not self.jsessionid:
            raise LinkedInAuthError("LINKEDIN_LI_AT and LINKEDIN_JSESSIONID must be configured.")

    @classmethod
    def from_env(cls):
        return cls(
            os.getenv("LINKEDIN_LI_AT", ""),
            os.getenv("LINKEDIN_JSESSIONID", ""),
            timeout=float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "20")),
        )

    def _headers(self) -> dict[str, str]:
        return {
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "x-restli-protocol-version": "2.0.0",
            # The CSRF token is the JSESSIONID value, verbatim.
            "csrf-token": self.jsessionid,
            "user-agent": os.getenv(
                "LINKEDIN_USER_AGENT",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
            ),
        }

    def fetch_profile(self, public_id: str) -> dict[str, Any]:
        params = {
            "q": "memberIdentity",
            "memberIdentity": public_id,
            "decorationId": self.query_decoration,
        }
        cookies = {"li_at": self.li_at, "JSESSIONID": self.jsessionid}

        with httpx.Client(
            base_url=BASE,
            headers=self._headers(),
            cookies=cookies,
            follow_redirects=False,
            timeout=self.timeout,
        ) as client:
            try:
                r = client.get(PROFILE_PATH, params=params)
            except httpx.HTTPError as exc:
                raise LinkedInUpstreamError(f"LinkedIn request failed: {exc}") from exc

        if r.status_code in (401, 403):
            raise LinkedInAuthError(
                "LinkedIn rejected the session (401/403). Refresh the li_at/JSESSIONID session."
            )
        if r.status_code == 429:
            raise LinkedInRateLimitError(
                "LinkedIn rate-limited the session. Stop sending requests and retry later."
            )
        if r.status_code >= 500:
            raise LinkedInUpstreamError(f"LinkedIn returned HTTP {r.status_code}.")
        if r.status_code != 200:
            raise LinkedInUpstreamError(
                f"LinkedIn returned HTTP {r.status_code}: {r.text[:300]}"
            )

        try:
            data = r.json()
        except ValueError as exc:
            raise LinkedInUpstreamError("LinkedIn returned non-JSON data.") from exc

        if not isinstance(data, dict):
            raise LinkedInUpstreamError("LinkedIn returned an unexpected JSON envelope.")

        return data
