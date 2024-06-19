"""Provide a mock standalone component."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

DOMAIN = "test_standalone"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Mock a successful setup."""
    return True
