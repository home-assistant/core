"""The Matrix bot component."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.components.notify import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_FORMAT,
    ATTR_IMAGES,
    ATTR_MESSAGE_ID,
    ATTR_REACTION,
    ATTR_ROOM,
    ATTR_THREAD_ID,
    CONF_ROOMS_REGEX,
    DOMAIN,
    FORMAT_HTML,
    FORMAT_TEXT,
    SERVICE_REACT,
    SERVICE_SEND_MESSAGE,
)

if TYPE_CHECKING:
    from . import MatrixBot


MESSAGE_FORMATS = [FORMAT_HTML, FORMAT_TEXT]
DEFAULT_MESSAGE_FORMAT = FORMAT_TEXT


SERVICE_SCHEMA_SEND_MESSAGE = probatio.Schema(
    {
        probatio.Required(ATTR_MESSAGE): cv.string,
        probatio.Optional(ATTR_DATA, default={}): {
            probatio.Optional(ATTR_FORMAT, default=DEFAULT_MESSAGE_FORMAT): probatio.In(
                MESSAGE_FORMATS
            ),
            probatio.Optional(ATTR_IMAGES): probatio.All(cv.ensure_list, [cv.string]),
            probatio.Optional(ATTR_THREAD_ID): cv.string,
        },
        probatio.Required(ATTR_TARGET): probatio.All(
            cv.ensure_list, [cv.matches_regex(CONF_ROOMS_REGEX)]
        ),
    }
)

SERVICE_SCHEMA_REACT = probatio.Schema(
    {
        probatio.Required(ATTR_REACTION): cv.string,
        probatio.Required(ATTR_ROOM): cv.matches_regex(CONF_ROOMS_REGEX),
        probatio.Required(ATTR_MESSAGE_ID): cv.string,
    }
)


async def _handle_send_message(call: ServiceCall) -> None:
    """Handle the send_message service call."""
    matrix_bot: MatrixBot = call.hass.data[DOMAIN]
    await matrix_bot.handle_send_message(call)


async def _handle_react(call: ServiceCall) -> None:
    """Handle the react service call."""
    matrix_bot: MatrixBot = call.hass.data[DOMAIN]
    await matrix_bot.handle_send_reaction(call)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Matrix bot component."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        _handle_send_message,
        schema=SERVICE_SCHEMA_SEND_MESSAGE,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REACT,
        _handle_react,
        schema=SERVICE_SCHEMA_REACT,
    )
