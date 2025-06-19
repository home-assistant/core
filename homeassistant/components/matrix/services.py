"""The Matrix bot component."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import voluptuous as vol

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


SERVICE_SCHEMA_SEND_MESSAGE = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_DATA, default={}): {
            vol.Optional(ATTR_FORMAT, default=DEFAULT_MESSAGE_FORMAT): vol.In(
                MESSAGE_FORMATS
            ),
            vol.Optional(ATTR_IMAGES): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_THREAD_ID): cv.string,
        },
        vol.Required(ATTR_TARGET): vol.All(
            cv.ensure_list, [cv.matches_regex(CONF_ROOMS_REGEX)]
        ),
    }
)

compiledEmojiRegex = re.compile(
    "[\U0001f600-\U0001f64f"  # Emoticons
    "\U0001f300-\U0001f5ff"  # Symbols & Pictographs
    "\U0001f680-\U0001f6ff"  # Transport & Map Symbols
    "\U0001f1e0-\U0001f1ff"  # Flags (iOS)
    "\U00002700-\U000027bf"  # Dingbats
    "\U00002600-\U000026ff"  # Miscellaneous Symbols
    "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
    "\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
    "\U00002500-\U00002bef"  # Chinese/Japanese/Korean characters
    "]+",
    flags=re.UNICODE,
)


def isEmoji(value: Any) -> str:
    """Validate that value is an emoji."""
    if not isinstance(value, str):
        raise vol.Invalid(f"not a string value: {value}")

    if not compiledEmojiRegex.match(value):
        raise vol.Invalid(f"value {value} is not a valid emoji")

    return value


SERVICE_SCHEMA_REACT = vol.Schema(
    {
        vol.Required(ATTR_REACTION): isEmoji,
        vol.Required(ATTR_ROOM): cv.matches_regex(CONF_ROOMS_REGEX),
        vol.Required(ATTR_MESSAGE_ID): cv.string,
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
