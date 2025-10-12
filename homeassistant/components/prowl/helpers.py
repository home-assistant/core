"""Helper functions for Prowl."""

import asyncio
from functools import partial

import prowlpy

from homeassistant.core import HomeAssistant


async def async_verify_key(hass: HomeAssistant, api_key: str) -> bool:
    """Validate API key."""
    prowl = await hass.async_add_executor_job(partial(prowlpy.Prowl, api_key))
    try:
        async with asyncio.timeout(10):
            await hass.async_add_executor_job(prowl.verify_key)
            return True
    except prowlpy.APIError as ex:
        if str(ex).startswith("Invalid API key"):
            return False
        raise
