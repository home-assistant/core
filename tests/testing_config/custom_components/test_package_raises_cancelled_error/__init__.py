"""Provide a mock package component."""

import asyncio


async def async_setup(hass, config):
    """Mock a successful setup."""
    asyncio.current_task().cancel()
    await asyncio.sleep(0)
