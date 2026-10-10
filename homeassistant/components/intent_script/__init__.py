"""Handle intents with scripts."""

import probatio

from homeassistant.components.script import CONF_MODE
from homeassistant.const import CONF_ACTION, CONF_DESCRIPTION, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, script
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ASYNC_ACTION,
    CONF_CARD,
    CONF_CONTENT,
    CONF_PLATFORMS,
    CONF_REPROMPT,
    CONF_SPEECH,
    CONF_TEXT,
    CONF_TITLE,
    DEFAULT_CONF_ASYNC_ACTION,
    DOMAIN,
)
from .helpers import async_load_intents
from .services import async_setup_services

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: {
            cv.string: {
                probatio.Optional(CONF_DESCRIPTION): cv.string,
                probatio.Optional(CONF_PLATFORMS): probatio.All(
                    [cv.string], probatio.Coerce(set)
                ),
                probatio.Optional(CONF_ACTION): cv.SCRIPT_SCHEMA,
                probatio.Optional(
                    CONF_ASYNC_ACTION, default=DEFAULT_CONF_ASYNC_ACTION
                ): cv.boolean,
                probatio.Optional(
                    CONF_MODE, default=script.DEFAULT_SCRIPT_MODE
                ): probatio.In(script.SCRIPT_MODE_CHOICES),
                probatio.Optional(CONF_CARD): {
                    probatio.Optional(CONF_TYPE, default="simple"): cv.string,
                    probatio.Required(CONF_TITLE): cv.template,
                    probatio.Required(CONF_CONTENT): cv.template,
                },
                probatio.Optional(CONF_SPEECH): {
                    probatio.Optional(CONF_TYPE, default="plain"): cv.string,
                    probatio.Required(CONF_TEXT): cv.template,
                },
                probatio.Optional(CONF_REPROMPT): {
                    probatio.Optional(CONF_TYPE, default="plain"): cv.string,
                    probatio.Required(CONF_TEXT): cv.template,
                },
            }
        }
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the intent script component."""
    intents = config[DOMAIN]

    await async_load_intents(hass, intents)

    async_setup_services(hass)

    return True
