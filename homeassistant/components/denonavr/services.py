"""Support for Denon AVR receivers using their HTTP interface."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import ATTR_COMMAND
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_DYNAMIC_EQ, DOMAIN

# Services
SERVICE_GET_COMMAND = "get_command"
SERVICE_SET_DYNAMIC_EQ = "set_dynamic_eq"
SERVICE_UPDATE_AUDYSSEY = "update_audyssey"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_COMMAND,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={vol.Required(ATTR_COMMAND): cv.string},
        func=f"async_{SERVICE_GET_COMMAND}",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_DYNAMIC_EQ,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={vol.Required(ATTR_DYNAMIC_EQ): cv.boolean},
        func=f"async_{SERVICE_SET_DYNAMIC_EQ}",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UPDATE_AUDYSSEY,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func=f"async_{SERVICE_UPDATE_AUDYSSEY}",
    )
