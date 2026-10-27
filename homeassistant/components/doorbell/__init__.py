"""Integration for doorbell triggers."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

DOMAIN = "doorbell"
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

__all__ = []


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    return True
