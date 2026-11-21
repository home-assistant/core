"""The device type vocabulary."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .types import SmartPlug

__all__ = ["SmartPlug"]

DOMAIN = "device_type"
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the device type integration."""
    return True
