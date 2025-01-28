"""The Home Assistant Hardware integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .helpers import HardwareInfoDispatcher

DOMAIN = "homeassistant_hardware"
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

DATA_COMPONENT: HassKey[HardwareInfoDispatcher] = HassKey(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""

    hass.data[DATA_COMPONENT] = HardwareInfoDispatcher(hass)

    return True
