"""LG webOS TV services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import ATTR_COMMAND
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import ATTR_PAYLOAD, ATTR_SOUND_OUTPUT, DOMAIN

ATTR_BUTTON = "button"

SERVICE_BUTTON = "button"
SERVICE_COMMAND = "command"
SERVICE_SELECT_SOUND_OUTPUT = "select_sound_output"

BUTTON_SCHEMA: VolDictType = {vol.Required(ATTR_BUTTON): cv.string}
COMMAND_SCHEMA: VolDictType = {
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Optional(ATTR_PAYLOAD): dict,
}
SOUND_OUTPUT_SCHEMA: VolDictType = {vol.Required(ATTR_SOUND_OUTPUT): cv.string}

SERVICES = (
    (
        SERVICE_BUTTON,
        BUTTON_SCHEMA,
        "async_button",
        SupportsResponse.NONE,
    ),
    (
        SERVICE_COMMAND,
        COMMAND_SCHEMA,
        "async_command",
        SupportsResponse.OPTIONAL,
    ),
    (
        SERVICE_SELECT_SOUND_OUTPUT,
        SOUND_OUTPUT_SCHEMA,
        "async_select_sound_output",
        SupportsResponse.OPTIONAL,
    ),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    for service_name, schema, method, supports_response in SERVICES:
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            service_name,
            entity_domain=MEDIA_PLAYER_DOMAIN,
            schema=schema,
            func=method,
            supports_response=supports_response,
        )
