"""Support for Alexa skill service end point."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entityfilter

from . import flash_briefings, intent, smart_home_http
from .const import (
    CONF_AUDIO,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DESCRIPTION,
    CONF_DISPLAY_CATEGORIES,
    CONF_DISPLAY_URL,
    CONF_ENDPOINT,
    CONF_ENTITY_CONFIG,
    CONF_FILTER,
    CONF_LOCALE,
    CONF_SUPPORTED_LOCALES,
    CONF_TEXT,
    CONF_TITLE,
    CONF_UID,
    DOMAIN,
    EVENT_ALEXA_SMART_HOME,
)

_LOGGER = logging.getLogger(__name__)

CONF_FLASH_BRIEFINGS = "flash_briefings"
CONF_SMART_HOME = "smart_home"
DEFAULT_LOCALE = "en-US"

ALEXA_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DESCRIPTION): cv.string,
        vol.Optional(CONF_DISPLAY_CATEGORIES): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)

SMART_HOME_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ENDPOINT): cv.string,
        vol.Optional(CONF_CLIENT_ID): cv.string,
        vol.Optional(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_LOCALE, default=DEFAULT_LOCALE): vol.In(
            CONF_SUPPORTED_LOCALES
        ),
        vol.Optional(CONF_FILTER, default={}): entityfilter.FILTER_SCHEMA,
        vol.Optional(CONF_ENTITY_CONFIG): {cv.entity_id: ALEXA_ENTITY_SCHEMA},
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            CONF_FLASH_BRIEFINGS: {
                cv.string: vol.All(
                    cv.ensure_list,
                    [
                        {
                            vol.Optional(CONF_UID): cv.string,
                            vol.Required(CONF_TITLE): cv.template,
                            vol.Optional(CONF_AUDIO): cv.template,
                            vol.Required(CONF_TEXT, default=""): cv.template,
                            vol.Optional(CONF_DISPLAY_URL): cv.template,
                        }
                    ],
                )
            },
            # vol.Optional here would mean we couldn't distinguish between an empty
            # smart_home: and none at all.
            CONF_SMART_HOME: vol.Any(SMART_HOME_SCHEMA, None),
        }
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Activate the Alexa component."""

    @callback
    def async_describe_logbook_event(event):
        """Describe a logbook event."""
        data = event.data
        entity_id = data["request"].get("entity_id")

        if entity_id:
            state = hass.states.get(entity_id)
            name = state.name if state else entity_id
            message = f"send command {data['request']['namespace']}/{data['request']['name']} for {name}"
        else:
            message = (
                f"send command {data['request']['namespace']}/{data['request']['name']}"
            )

        return {
            "name": "Amazon Alexa",
            "message": message,
            "entity_id": entity_id,
        }

    hass.components.logbook.async_describe_event(
        DOMAIN, EVENT_ALEXA_SMART_HOME, async_describe_logbook_event
    )

    if DOMAIN not in config:
        return True

    config = config[DOMAIN]

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
        await smart_home_http.async_setup(hass, smart_home_config)

    return True
