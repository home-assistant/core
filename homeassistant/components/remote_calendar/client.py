"""Specifies the parameter for the httpx download."""

from httpx import AsyncClient, Response, Timeout


async def get_calendar(client: AsyncClient, url: str) -> Response:
    """Make an HTTP GET request using Home Assistant's async HTTPX client with timeout."""
    return await client.get(
        url,
        follow_redirects=True,
        timeout=Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0),
    )
