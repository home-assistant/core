"""Services for the monoprice integration."""

from __future__ import annotations

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN, SERVICE_RESTORE, SERVICE_SNAPSHOT


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SNAPSHOT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="snapshot",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RESTORE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="restore",
    )
