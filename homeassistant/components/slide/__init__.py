"""Component for the Slide API."""

import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

from .const import COMPONENT_PLATFORM, CONF_API_VERSION, CONF_INVERT_POSITION, DOMAIN

_LOGGER = logging.getLogger(__name__)

COVER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD, default=""): cv.string,
        vol.Optional(CONF_INVERT_POSITION, default=False): cv.boolean,
        vol.Optional(CONF_API_VERSION, default=2): cv.byte,
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(cv.ensure_list, [vol.Any(COVER_SCHEMA)]),
    },
    extra=vol.ALLOW_EXTRA,
)


#################################################################
async def async_setup(hass, config):
    """Set up the local Slide platform."""

    if DOMAIN not in config:
        _LOGGER.info("Slide not configured")
        return True

    _LOGGER.debug("Initializing Slide platform")

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][COMPONENT_PLATFORM] = False

    for cover in config[DOMAIN]:
        hass.async_create_task(
            async_load_platform(hass, COMPONENT_PLATFORM, DOMAIN, cover, config)
        )

    return True
