"""File contains helper functions that are used in various places."""

import aiohttp
from aiopapouch import PapouchHTTPClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_WEB_PORT


async def _get_device_name(
    hass: HomeAssistant,
    ip_address: str,
    password: str = "",
    web_port: int = DEFAULT_WEB_PORT,
) -> str:
    """Fetch the real device name and location directly from the device."""
    session = async_get_clientsession(hass)
    client = PapouchHTTPClient(
        ip_address, session, password=password, web_port=web_port
    )
    try:
        name, location = await client.get_device_info()
        if name and location:
            return f"{name} ({location})"
    except aiohttp.ClientError:
        pass

    return "Papouch Device"
