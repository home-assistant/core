"""The rasc integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_NAME, DOMAIN_RASCALSCHEDULER
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.typing import ConfigType

from .abstraction import RASCAbstraction
from .const import DOMAIN, LOGGER
from .scheduler import RascalScheduler

DEFAULT_NAME = "RASCal Abstraction"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the RASC component."""
    component = hass.data[DOMAIN] = RASCAbstraction(LOGGER, DOMAIN, hass)
    hass.data[DOMAIN_RASCALSCHEDULER] = RascalScheduler(hass)

    await component.async_load()

    return True
