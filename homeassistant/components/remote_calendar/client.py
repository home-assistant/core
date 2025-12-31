"""Specifies the parameter for the httpx download."""

from httpx import AsyncClient, Response, Timeout


async def get_calendar(
    client: AsyncClient, url: str, user_agent: str | None = None
) -> Response:
    """Make an HTTP GET request using Home Assistant's async HTTPX client with timeout."""
    headers = None
    if user_agent is not None:
        headers = {b"User-Agent": user_agent.encode("ascii")}
    return await client.get(
        url,
        follow_redirects=True,
        timeout=Timeout(5, read=30, write=5, pool=5),
        headers=headers,
    )
