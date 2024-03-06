"""Provide a mock package component."""
import asyncio


async def async_setup(hass, config):
    """Mock a successful setup."""
    raise asyncio.CancelledError("Make sure this does not leak upward")
