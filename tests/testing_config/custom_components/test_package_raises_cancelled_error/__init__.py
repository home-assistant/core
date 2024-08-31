"""Provide a mock package component."""

import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Mock a successful setup."""
    asyncio.current_task().cancel()
    await asyncio.sleep(0)
