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
TRACKLIST_ORDER_BY_REGISTER_TIME_ASC = "11"
TRACKLIST_TIME_ZONE_OFFSET = 0

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Safari/537.36"
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


def _is_archived(package: dict[str, Any]) -> bool:
    """Return whether a package is archived according to the API response."""
    return bool(
        package.get("archived")
        or package.get("is_archived")
        or package.get("is_archive")
        or package.get("archived_at")
    )


def _package_value(package: dict[str, Any], key: str) -> str | None:
    """Return a string package value."""
    value = package.get(key)
    if isinstance(value, str):
        return value

    return None


def _parse_datetime(value: str | None) -> str:
    """Parse an ISO timestamp from the 17Track API for pyseventeentrack."""
    if not value:
        return ""

    try:
        parsed = datetime.fromisoformat(value)
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

    async def _tracklist(self, show_archived: bool = False) -> list[dict[str, Any]]:
        """Get package data from the current 17Track track list API."""
        tracklist_resp: dict[str, Any] = await self._request(
            "post",
            API_URL,
            json={
                "page_no": 1,
                "order_by": TRACKLIST_ORDER_BY_REGISTER_TIME_ASC,
                "timeZoneOffset": TRACKLIST_TIME_ZONE_OFFSET,
            },
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

        data = tracklist_resp.get("data")
        if not isinstance(data, dict):
            return []

        accepted = data.get("accepted")
        if not isinstance(accepted, list):
            return []

        packages = [package for package in accepted if isinstance(package, dict)]
        if show_archived:
            return packages

        return [package for package in packages if not _is_archived(package)]

    async def packages(
        self,
        package_state: int | str = "",
        show_archived: bool = False,
        tz: str = "UTC",
    ) -> list[Package]:
        """Get the list of packages associated with the account."""
        packages = []
        for package in await self._tracklist(show_archived=show_archived):
            tracking_number = _package_value(package, "number")
            if not tracking_number:
                continue

            status = _package_status(package)
            if package_state != "" and package_state not in (status, str(status)):
                continue

            packages.append(
                Package(
                    tracking_number,
                    destination_country=0,
                    friendly_name=_package_value(package, "tag")
                    or _package_value(package, "remark"),
                    info_text=_package_value(package, "latest_event_info"),
                    timestamp=_parse_datetime(
                        _package_value(package, "latest_event_time")
                    ),
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
            for package in await self._tracklist(show_archived=show_archived)
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
        request_headers = self._headers_for_url(str(url))
        if headers:
            request_headers.update(headers)

        return await super()._request(
            method,
            url,
            headers=request_headers,
            params=params,
            json=json,
        )

    def _headers_for_url(self, url: str | URL) -> dict[str, str]:
        """Return browser-like headers for a 17Track API URL."""
        request_url = URL(str(url))
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json;charset=UTF-8",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "User-Agent": BROWSER_USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
        }

        if request_url.host == USER_URL.host and request_url.path == USER_URL.path:
            headers["Origin"] = "https://www.17track.net"
            headers["Referer"] = "https://www.17track.net/"
            headers["Sec-Fetch-Site"] = "same-site"
            return headers

        if (
            request_url.host == API_TRACK_URL.host
            and request_url.path == API_TRACK_URL.path
        ):
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
