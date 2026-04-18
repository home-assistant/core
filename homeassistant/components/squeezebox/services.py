"""Support for interfacing to the SqueezeBox API."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import ATTR_COMMAND
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_CALL_METHOD = "call_method"
SERVICE_CALL_QUERY = "call_query"

ATTR_PARAMETERS = "parameters"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CALL_METHOD,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Required(ATTR_COMMAND): cv.string,
            vol.Optional(ATTR_PARAMETERS): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
        },
        func="async_call_method",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CALL_QUERY,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Required(ATTR_COMMAND): cv.string,
            vol.Optional(ATTR_PARAMETERS): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
        },
        func="async_call_query",
    )
