"""
Support for Alexa skill service end point.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/alexa/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entityfilter

from . import flash_briefings, intent, smart_home
from .const import (
    CONF_AUDIO, CONF_DISPLAY_URL, CONF_TEXT, CONF_TITLE, CONF_UID, DOMAIN,
    CONF_FILTER, CONF_ENTITY_CONFIG)

_LOGGER = logging.getLogger(__name__)

CONF_FLASH_BRIEFINGS = 'flash_briefings'
CONF_SMART_HOME = 'smart_home'

DEPENDENCIES = ['http']

ALEXA_ENTITY_SCHEMA = vol.Schema({
    vol.Optional(smart_home.CONF_DESCRIPTION): cv.string,
    vol.Optional(smart_home.CONF_DISPLAY_CATEGORIES): cv.string,
    vol.Optional(smart_home.CONF_NAME): cv.string,
})

SMART_HOME_SCHEMA = vol.Schema({
    vol.Optional(CONF_FILTER, default={}): entityfilter.FILTER_SCHEMA,
    vol.Optional(CONF_ENTITY_CONFIG): {cv.entity_id: ALEXA_ENTITY_SCHEMA}
})

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
        },
        # vol.Optional here would mean we couldn't distinguish between an empty
        # smart_home: and none at all.
        CONF_SMART_HOME: vol.Any(SMART_HOME_SCHEMA, None),
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

    try:
        smart_home_config = config[CONF_SMART_HOME]
    except KeyError:
        pass
    else:
        smart_home_config = smart_home_config or SMART_HOME_SCHEMA({})
        smart_home.async_setup(hass, smart_home_config)

    return True
