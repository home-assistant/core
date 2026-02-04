"""The Matrix bot component."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.notify import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CONFIG_ENTRY_ID,
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
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
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

SERVICE_SCHEMA_REACT = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_REACTION): cv.string,
        vol.Required(ATTR_ROOM): cv.matches_regex(CONF_ROOMS_REGEX),
        vol.Required(ATTR_MESSAGE_ID): cv.string,
    }
)

def _match_bots_for_rooms(
    matrix_data: dict[str, MatrixBot], target_rooms: list[str]
) -> list[MatrixBot]:
    matches: list[MatrixBot] = []
    for matrix_bot in matrix_data.values():
        known_rooms = (
            set(matrix_bot._configured_rooms)
            | set(matrix_bot._listening_rooms)
            | set(matrix_bot._listening_rooms.values())
        )
        if any(room in known_rooms for room in target_rooms):
            matches.append(matrix_bot)
    return matches


def _get_matrix_bot(
    call: ServiceCall, target_rooms: list[str] | None = None
) -> MatrixBot:
    """Resolve the MatrixBot to use for a service call."""
    matrix_data = call.hass.data.get(DOMAIN)
    if not matrix_data:
        raise ServiceValidationError("You do not have any Matrix config entries loaded")

    if not isinstance(matrix_data, Mapping):
        return matrix_data

    config_entry_id = call.data.get(CONF_CONFIG_ENTRY_ID)
    if config_entry_id is not None:
        if config_entry := matrix_data.get(config_entry_id):
            return config_entry
        raise ServiceValidationError(
            "No Matrix config entry found for the provided config entry id"
        )

    if len(matrix_data) == 1:
        return next(iter(matrix_data.values()))

    if target_rooms:
        matches = _match_bots_for_rooms(matrix_data, target_rooms)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ServiceValidationError(
                "Multiple Matrix config entries match the target rooms. "
                "Set config_entry_id to choose one."
            )

    raise ServiceValidationError(
        "Multiple Matrix config entries are loaded. Set config_entry_id to choose one."
    )


async def _handle_send_message(call: ServiceCall) -> None:
    """Handle the send_message service call."""
    matrix_bot = _get_matrix_bot(call, call.data.get(ATTR_TARGET))
    await matrix_bot.handle_send_message(call)


async def _handle_react(call: ServiceCall) -> None:
    """Handle the react service call."""
    matrix_bot = _get_matrix_bot(call, [call.data[ATTR_ROOM]])
    await matrix_bot.handle_send_reaction(call)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Matrix bot component."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE):
        return

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
