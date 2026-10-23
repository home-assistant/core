"""The Weather data integration.

Combines weather entities and local sensors into one view of the weather at
home: the preferred order of weather sources, and the sensors for rain, air
quality and pollen.
"""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DOMAIN

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Weather data integration."""
    websocket_api.async_setup(hass)
    return True
