"""The Bizkaibus bus tracker component."""

import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_STOP_ID

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend({vol.Required(CONF_STOP_ID): cv.string})
CONFIG_SCHEMA = vol.Schema({vol.Required(CONF_STOP_ID): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Bizkaibus component."""
    # hass.states.async_set("hello_state.world", "Paulus")

    # Return boolean to indicate that initialization was successful.
    return True
