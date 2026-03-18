"""The Matrix bot component."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.notify import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_FORMAT,
    ATTR_IMAGES,
    CONF_ROOMS_REGEX,
    DOMAIN,
    FORMAT_HTML,
    FORMAT_TEXT,
    SERVICE_SEND_MESSAGE,
)

if TYPE_CHECKING:
    from . import MatrixBot


MESSAGE_FORMATS = [FORMAT_HTML, FORMAT_TEXT]
DEFAULT_MESSAGE_FORMAT = FORMAT_TEXT


SERVICE_SCHEMA_SEND_MESSAGE = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_DATA, default={}): {
            vol.Optional(ATTR_FORMAT, default=DEFAULT_MESSAGE_FORMAT): vol.In(
                MESSAGE_FORMATS
            ),
            vol.Optional(ATTR_IMAGES): vol.All(cv.ensure_list, [cv.string]),
        },
        vol.Required(ATTR_TARGET): vol.All(
            cv.ensure_list, [cv.matches_regex(CONF_ROOMS_REGEX)]
        ),
    }
)


async def _handle_send_message(call: ServiceCall) -> None:
    """Handle the send_message service call."""
    matrix_bot: MatrixBot = call.hass.data[DOMAIN]
    await matrix_bot.handle_send_message(call)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Matrix bot component."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        _handle_send_message,
        schema=SERVICE_SCHEMA_SEND_MESSAGE,
    )
