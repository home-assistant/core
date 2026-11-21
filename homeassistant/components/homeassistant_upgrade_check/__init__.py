"""The Home Assistant Upgrade Check integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DOMAIN
from .feed import DATA_FEED, ReleaseFeed

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the upgrade check."""
    hass.data[DATA_FEED] = ReleaseFeed(hass)
    websocket_api.async_setup(hass)
    # Mock: without a Supervisor there is no core update to check against.
    if not is_hassio(hass):
        hass.async_create_task(
            discovery.async_load_platform(hass, Platform.UPDATE, DOMAIN, {}, config)
        )
    # /Mock
    return True
