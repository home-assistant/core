"""Rain Bird integration API helpers."""

from __future__ import annotations

import aiohttp
from pyrainbird.async_client import AsyncRainbirdController, create_controller


async def async_create_controller(
    clientsession: aiohttp.ClientSession,
    host: str,
    password: str,
) -> AsyncRainbirdController:
    """Create a pyrainbird controller."""
    return await create_controller(clientsession, host, password)
