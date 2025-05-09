"""The Hardware integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DATA_HARDWARE, DOMAIN
from .models import HardwareData

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Hardware."""
    hass.data[DATA_HARDWARE] = HardwareData()

    await websocket_api.async_setup(hass)

    return True
