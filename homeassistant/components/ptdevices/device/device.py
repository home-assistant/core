"""Functions for communication with PTDevices via the aioptdevices package."""

from __future__ import annotations

import asyncio

from aiohttp import CookieJar
from aioptdevices.configuration import Configuration
from aioptdevices.interface import Interface, PTDevicesResponse

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from ..const import DEFAULT_URL


async def ptdevices_get_data(
    hass: HomeAssistant,
    authToken: str,
    deviceId: str,
) -> PTDevicesResponse:
    """Request device data, format and return it."""
    # Create web session for use when communicating
    session = aiohttp_client.async_create_clientsession(
        hass, cookie_jar=CookieJar(unsafe=True)
    )
    # Setup interface to PTDevices
    interface = Interface(
        Configuration(
            auth_token=authToken,
            device_id=deviceId,
            url=DEFAULT_URL,
            session=session,
        )
    )

    # Get device data from PTDevices server

    async with asyncio.timeout(10):
        data: PTDevicesResponse = await interface.get_data()

    return data
