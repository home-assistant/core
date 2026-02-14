"""MediaPlayer platform for Roon integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_TRANSFER = "transfer"

ATTR_TRANSFER = "transfer_id"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_TRANSFER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={vol.Required(ATTR_TRANSFER): cv.entity_id},
        func="async_transfer",
    )
