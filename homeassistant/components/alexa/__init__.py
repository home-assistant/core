"""
Support for Alexa skill service end point.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/alexa/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN, CONF_UID, CONF_TITLE, CONF_AUDIO, CONF_TEXT, CONF_DISPLAY_URL)
from . import flash_briefings, intent

_LOGGER = logging.getLogger(__name__)


DEPENDENCIES = ['http']

CONF_FLASH_BRIEFINGS = 'flash_briefings'


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        CONF_FLASH_BRIEFINGS: {
            cv.string: vol.All(cv.ensure_list, [{
                vol.Optional(CONF_UID): cv.string,
                vol.Required(CONF_TITLE): cv.template,
                vol.Optional(CONF_AUDIO): cv.template,
                vol.Required(CONF_TEXT, default=""): cv.template,
                vol.Optional(CONF_DISPLAY_URL): cv.template,
            }]),
        }
    }
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Activate Alexa component."""
    config = config.get(DOMAIN, {})
    flash_briefings_config = config.get(CONF_FLASH_BRIEFINGS)

    intent.async_setup(hass)

    if flash_briefings_config:
        flash_briefings.async_setup(hass, flash_briefings_config)

    return True
