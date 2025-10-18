"""Helper functions for Prowl."""

import asyncio

import prowlpy

from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client


async def async_verify_key(hass: HomeAssistant, api_key: str) -> bool:
    """Validate API key."""
    prowl = prowlpy.AsyncProwl(api_key, client=get_async_client(hass))
    try:
        async with asyncio.timeout(10):
            await prowl.verify_key()
            return True
    except prowlpy.InvalidAPIKeyError:
        return False
