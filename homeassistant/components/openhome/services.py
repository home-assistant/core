"""Support for Openhome Devices."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_INVOKE_PIN = "invoke_pin"
ATTR_PIN_INDEX = "pin"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_INVOKE_PIN,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={vol.Required(ATTR_PIN_INDEX): cv.positive_int},
        func="async_invoke_pin",
    )
