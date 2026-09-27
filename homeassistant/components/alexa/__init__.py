"""Support for Alexa skill service end point."""

from typing import Any

import probatio

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DESCRIPTION,
    CONF_NAME,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entityfilter
from homeassistant.helpers.typing import ConfigType

from . import flash_briefings, intent, smart_home
from .const import (
    CONF_AUDIO,
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
)

CONF_FLASH_BRIEFINGS = "flash_briefings"
CONF_SMART_HOME = "smart_home"
DEFAULT_LOCALE = "en-US"

# Alexa Smart Home API send events gateway endpoints
# https://developer.amazon.com/en-US/docs/alexa/smarthome/send-events.html#endpoints
VALID_ENDPOINTS = [
    "https://api.amazonalexa.com/v3/events",
    "https://api.eu.amazonalexa.com/v3/events",
    "https://api.fe.amazonalexa.com/v3/events",
]


ALEXA_ENTITY_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_DESCRIPTION): cv.string,
        probatio.Optional(CONF_DISPLAY_CATEGORIES): cv.string,
        probatio.Optional(CONF_NAME): cv.string,
    }
)

SMART_HOME_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_ENDPOINT): probatio.All(
            probatio.Lower, probatio.In(VALID_ENDPOINTS)
        ),
        probatio.Optional(CONF_CLIENT_ID): cv.string,
        probatio.Optional(CONF_CLIENT_SECRET): cv.string,
        probatio.Optional(CONF_LOCALE, default=DEFAULT_LOCALE): probatio.In(
            CONF_SUPPORTED_LOCALES
        ),
        probatio.Optional(CONF_FILTER, default={}): entityfilter.FILTER_SCHEMA,
        probatio.Optional(CONF_ENTITY_CONFIG): {cv.entity_id: ALEXA_ENTITY_SCHEMA},
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: {
            CONF_FLASH_BRIEFINGS: {
                probatio.Required(CONF_PASSWORD): cv.string,
                cv.string: probatio.All(
                    cv.ensure_list,
                    [
                        {
                            probatio.Optional(CONF_UID): cv.string,
                            probatio.Required(CONF_TITLE): cv.template,
                            probatio.Optional(CONF_AUDIO): cv.template,
                            probatio.Required(CONF_TEXT, default=""): cv.template,
                            probatio.Optional(CONF_DISPLAY_URL): cv.template,
                        }
                    ],
                ),
            },
            # probatio.Optional here would mean we couldn't distinguish between an empty
            # smart_home: and none at all.
            CONF_SMART_HOME: probatio.Any(SMART_HOME_SCHEMA, None),
        }
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Activate the Alexa component."""
    if DOMAIN not in config:
        return True

    config = config[DOMAIN]

    intent.async_setup(hass)

    if flash_briefings_config := config.get(CONF_FLASH_BRIEFINGS):
        flash_briefings.async_setup(hass, flash_briefings_config)

    # smart_home being absent is not the same as smart_home being None
    if CONF_SMART_HOME in config:
        smart_home_config: dict[str, Any] | None = config[CONF_SMART_HOME]
        smart_home_config = smart_home_config or SMART_HOME_SCHEMA({})
        await smart_home.async_setup(hass, smart_home_config)

    return True
