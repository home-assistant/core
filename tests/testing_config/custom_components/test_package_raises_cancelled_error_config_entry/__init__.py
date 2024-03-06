"""Provide a mock package component."""
import asyncio


async def async_setup(hass, config):
    """Mock a successful setup."""
    return True


async def async_setup_entry(hass, entry):
    """Mock an unsuccessful entry setup."""
    raise asyncio.CancelledError("Make sure this does not leak upward")
