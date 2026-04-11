"""Support for LinkPlay media players."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_PLAY_PRESET = "play_preset"
ATTR_PRESET_NUMBER = "preset_number"

SERVICE_PLAY_PRESET_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_PRESET_NUMBER): cv.positive_int,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_PLAY_PRESET,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=SERVICE_PLAY_PRESET_SCHEMA,
        func="async_play_preset",
    )
