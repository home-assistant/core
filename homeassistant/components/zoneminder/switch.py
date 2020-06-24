"""Support for ZoneMinder switches."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_COMMAND_OFF, CONF_COMMAND_ON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_COMMAND_ON): cv.string,
        vol.Optional(CONF_COMMAND_OFF): cv.string,
    }
)


def setup_platform(hass: HomeAssistant, config, add_entities, discovery_info=None):
    """Set up the ZoneMinder switch platform."""
    _LOGGER.warning(
        "ZoneMinder switch platform is no longer supported as this functionality is easily handled using a switch template."
    )
