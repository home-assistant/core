"""Services for the Google Assistant SDK integration."""

from __future__ import annotations

import dataclasses

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .helpers import async_send_text_commands

SERVICE_SEND_TEXT_COMMAND = "send_text_command"
SERVICE_SEND_TEXT_COMMAND_FIELD_COMMAND = "command"
SERVICE_SEND_TEXT_COMMAND_FIELD_MEDIA_PLAYER = "media_player"
SERVICE_SEND_TEXT_COMMAND_SCHEMA = vol.All(
    {
        vol.Required(SERVICE_SEND_TEXT_COMMAND_FIELD_COMMAND): vol.All(
            cv.ensure_list, [vol.All(str, vol.Length(min=1))]
        ),
        vol.Optional(SERVICE_SEND_TEXT_COMMAND_FIELD_MEDIA_PLAYER): cv.comp_entity_ids,
    },
)


async def _send_text_command(call: ServiceCall) -> ServiceResponse:
    """Send a text command to Google Assistant SDK."""
    commands: list[str] = call.data[SERVICE_SEND_TEXT_COMMAND_FIELD_COMMAND]
    media_players: list[str] | None = call.data.get(
        SERVICE_SEND_TEXT_COMMAND_FIELD_MEDIA_PLAYER
    )
    command_response_list = await async_send_text_commands(
        call.hass, commands, media_players
    )
    if call.return_response:
        return {
            "responses": [
                dataclasses.asdict(command_response)
                for command_response in command_response_list
            ]
        }
    return None


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Add the services for Google Assistant SDK."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_TEXT_COMMAND,
        _send_text_command,
        schema=SERVICE_SEND_TEXT_COMMAND_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
