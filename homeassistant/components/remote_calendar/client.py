"""HTTP client for fetching remote calendar data."""

from ipaddress import ip_address
from urllib.parse import urlparse

from httpx import AsyncClient, Auth, BasicAuth, InvalidURL, Response, Timeout

from homeassistant.util.network import is_invalid, is_local


def _validate_url(url: str) -> None:
    """Raise InvalidURL if the URL targets an internal or private network address."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise InvalidURL(f"Invalid URL scheme: {parsed.scheme!r}")
    host = parsed.hostname or ""
    try:
        addr = ip_address(host)
        if is_local(addr) or is_invalid(addr):
            raise InvalidURL(f"URL targets a private/internal address: {host!r}")
    except ValueError:
        pass  # hostname rather than IP address — skip IP-range check


async def get_calendar(
    client: AsyncClient,
    url: str,
    username: str | None = None,
    password: str | None = None,
) -> Response:
    """Make an HTTP GET request using Home Assistant's async HTTPX client with timeout."""
    _validate_url(url)
    auth: Auth | None = None
    if username is not None and password is not None:
        auth = BasicAuth(username, password)

    return await client.get(
        url,
        auth=auth,
        follow_redirects=True,
        timeout=Timeout(5, read=30, write=5, pool=5),
    )
