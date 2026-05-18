"""17Track API client helpers."""

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from pyseventeentrack import Client as SeventeenTrackClient
from pyseventeentrack.errors import NotLoggedInError, SeventeenTrackError
from pyseventeentrack.package import Package
from pyseventeentrack.profile import API_URL_USER, Profile
from yarl import URL

API_URL = "https://api.17track.net/track/v2.4/gettracklist"
API_TRACK_URL = URL(API_URL)
USER_URL = URL(API_URL_USER)

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

PACKAGE_STATUS = {
    "NotFound": 0,
    "InfoReceived": 10,
    "InTransit": 10,
    "Expired": 20,
    "PickUp": 30,
    "Undelivered": 35,
    "Delivered": 40,
    "Alert": 50,
}
STATUS_NAMES = {
    0: "Not Found",
    10: "In Transit",
    20: "Expired",
    30: "Ready to be Picked Up",
    35: "Undelivered",
    40: "Delivered",
    50: "Alert",
}


def _parse_datetime(value: str | None) -> str:
    """Parse an ISO timestamp from the 17Track API for pyseventeentrack."""
    if not value:
        return ""

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""

    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _package_status(package: dict[str, Any]) -> int:
    """Return the Home Assistant package status code."""
    api_status = package.get("package_status")
    if not isinstance(api_status, str):
        return 0

    return PACKAGE_STATUS.get(api_status, 0)


class ModernProfile(Profile):
    """Profile manager using the current 17Track web API."""

    async def _tracklist(self) -> list[dict[str, Any]]:
        """Get package data from the current 17Track track list API."""
        tracklist_resp: dict[str, Any] = await self._request(
            "post",
            API_URL,
            json={"page_no": 1, "order_by": "11", "timeZoneOffset": 0},
        )

        code = (tracklist_resp or {}).get("code", 0)
        if code == -6:
            raise NotLoggedInError(
                f"Not logged in (Code: {code}, Message: "
                f"{(tracklist_resp or {}).get('message')})"
            )

        if code != 0:
            raise SeventeenTrackError(
                f"17TRACK API error (Code: {code}, Message: "
                f"{(tracklist_resp or {}).get('message')})"
            )

        return (tracklist_resp.get("data") or {}).get("accepted") or []

    async def packages(
        self,
        package_state: int | str = "",
        show_archived: bool = False,
        tz: str = "UTC",
    ) -> list[Package]:
        """Get the list of packages associated with the account."""
        packages = []
        for package in await self._tracklist():
            status = _package_status(package)
            if package_state and package_state not in (status, str(status)):
                continue

            packages.append(
                Package(
                    package["number"],
                    destination_country=0,
                    friendly_name=package.get("tag") or package.get("remark"),
                    info_text=package.get("latest_event_info"),
                    timestamp=_parse_datetime(package.get("latest_event_time")),
                    origin_country=0,
                    package_type=0,
                    status=status,
                    tz=tz,
                )
            )

        return packages

    async def summary(self, show_archived: bool = False) -> dict[str, int]:
        """Get a quick summary of how many packages are in an account."""
        summary = Counter(
            STATUS_NAMES[_package_status(package)]
            for package in await self._tracklist()
        )

        return {status: summary[status] for status in STATUS_NAMES.values()}


class BrowserLikeSeventeenTrackClient(SeventeenTrackClient):
    """17Track client that sends browser-like request headers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize."""
        super().__init__(*args, **kwargs)
        self.profile = ModernProfile(self._request)

    def copy_login_cookies_to_api_domain(self) -> None:
        """Copy login cookies to the current track API domain."""
        if not self._session:
            return

        login_cookies = self._session.cookie_jar.filter_cookies(USER_URL)
        if login_cookies:
            self._session.cookie_jar.update_cookies(login_cookies, API_TRACK_URL)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a request with headers expected by the 17Track web API."""
        request_headers = self._headers_for_url(url)
        if headers:
            request_headers.update(headers)

        return await super()._request(
            method,
            url,
            headers=request_headers,
            params=params,
            json=json,
        )

    def _headers_for_url(self, url: str) -> dict[str, str]:
        """Return browser-like headers for a 17Track API URL."""
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json;charset=UTF-8",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "User-Agent": BROWSER_USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
        }

        if url == API_URL_USER:
            headers["Origin"] = "https://www.17track.net"
            headers["Referer"] = "https://www.17track.net/"
            headers["Sec-Fetch-Site"] = "same-site"
            return headers

        if str(url).startswith(API_URL):
            headers["Accept"] = "*/*"
            headers["Content-Type"] = "application/json"
            headers["Origin"] = "https://admin.17track.net"
            headers["Referer"] = "https://admin.17track.net/"
            headers["Sec-Fetch-Site"] = "same-site"

            if self._session:
                cookies = self._session.cookie_jar.filter_cookies(API_TRACK_URL)
                if csrf_token := cookies.get("csrf_token"):
                    headers["x-csrf-token"] = csrf_token.value

            return headers

        return headers
