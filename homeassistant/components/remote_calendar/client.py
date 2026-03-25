"""HTTP client for fetching remote calendar data."""

from httpx import AsyncClient, Auth, BasicAuth, Response, Timeout


async def get_calendar(
    client: AsyncClient,
    url: str,
    username: str | None = None,
    password: str | None = None,
) -> Response:
    """Make an HTTP GET request using Home Assistant's async HTTPX client with timeout."""
    auth: Auth | None = None
    if username is not None and password is not None:
        auth = BasicAuth(username, password)

    return await client.get(
        url,
        auth=auth,
        follow_redirects=True,
        timeout=Timeout(5, read=30, write=5, pool=5),
    )
