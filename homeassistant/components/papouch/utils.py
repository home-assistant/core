"""File contains helper functions that are used in various places."""

from typing import TYPE_CHECKING

import aiohttp
from aiopapouch import PapouchHTTPClient

from homeassistant.helpers.aiohttp_client import async_get_clientsession

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def _get_device_name(
    hass: HomeAssistant, ip_address: str, password: str = ""
) -> str:
    """Fetch the real device name and location directly from the device."""
    session = async_get_clientsession(hass)
    client = PapouchHTTPClient(ip_address, session, password=password)
    try:
        name, location = await client.get_device_info()
        if name and location:
            return f"{name} ({location})"
    except aiohttp.ClientError:
        pass

    return "Papouch Device"
