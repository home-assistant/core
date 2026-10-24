"""File contains helper functions that are used in various places."""

import aiohttp
from aiopapouch import PapouchHTTPClient

from .const import DEFAULT_WEB_PORT


async def _get_device_name(
    session: aiohttp.ClientSession,
    ip_address: str,
    password: str = "",
    web_port: int = DEFAULT_WEB_PORT,
) -> str:
    """Fetch the real device name and location directly from the device. Doesn't raise."""

    client = PapouchHTTPClient(
        ip_address, session, password=password, web_port=web_port
    )

    try:
        name, location = await client.get_device_info()
        if name and location:
            return f"{name} ({location})"
        if name and not location:
            return f"{name} (NONAME)"
        if not name and location:
            return f"Papouch device ({location})"
    except aiohttp.ClientError:
        pass

    return "Papouch Device - (NONAME)"
