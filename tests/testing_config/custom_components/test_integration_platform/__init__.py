"""Provide a mock package component."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import TEST  # noqa: F401

DOMAIN = "test_integration_platform"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Mock a successful setup."""
    return True
