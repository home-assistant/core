"""Provide a mock package component."""

import asyncio


async def async_setup(hass, config):
    """Mock a successful setup."""
    return True


async def async_setup_entry(hass, entry):
    """Mock an unsuccessful entry setup."""
    asyncio.current_task().cancel()
    await asyncio.sleep(0)
