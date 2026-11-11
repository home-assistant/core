"""The Matrix bot component."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_FORMAT,
    ATTR_IMAGES,
    ATTR_THREAD_ID,
    CONF_ROOMS_REGEX,
    DOMAIN,
    FORMAT_HTML,
    FORMAT_TEXT,
    MatrixService,
    MatrixServiceArgument,
)

if TYPE_CHECKING:
    from . import MatrixBot


MESSAGE_FORMATS = [FORMAT_HTML, FORMAT_TEXT]
DEFAULT_MESSAGE_FORMAT = FORMAT_TEXT


SERVICE_SCHEMA_SEND_MESSAGE = probatio.Schema(
    {
        probatio.Required(MatrixServiceArgument.MESSAGE): cv.string,
        probatio.Optional(MatrixServiceArgument.DATA, default={}): {
            probatio.Optional(ATTR_FORMAT, default=DEFAULT_MESSAGE_FORMAT): probatio.In(
                MESSAGE_FORMATS
            ),
            probatio.Optional(ATTR_IMAGES): probatio.All(
                probatio.EnsureList(), [cv.string]
            ),
            probatio.Optional(ATTR_THREAD_ID): cv.string,
        },
        probatio.Required(MatrixServiceArgument.TARGET): probatio.All(
            probatio.EnsureList(), [cv.matches_regex(CONF_ROOMS_REGEX)]
        ),
    }
)

SERVICE_SCHEMA_REACT = probatio.Schema(
    {
        probatio.Required(MatrixServiceArgument.REACTION): cv.string,
        probatio.Required(MatrixServiceArgument.ROOM): cv.matches_regex(
            CONF_ROOMS_REGEX
        ),
        probatio.Required(MatrixServiceArgument.MESSAGE_ID): cv.string,
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
        MatrixService.SEND_MESSAGE,
        _handle_send_message,
        schema=SERVICE_SCHEMA_SEND_MESSAGE,
    )

    hass.services.async_register(
        DOMAIN,
        MatrixService.REACT,
        _handle_react,
        schema=SERVICE_SCHEMA_REACT,
    )
