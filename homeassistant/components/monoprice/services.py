"""Services for the monoprice integration."""

from enum import StrEnum

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN


class MonopriceService(StrEnum):
    """Store keys for Monoprice services."""

    SNAPSHOT = "snapshot"
    RESTORE = "restore"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MonopriceService.SNAPSHOT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="snapshot",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MonopriceService.RESTORE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="restore",
    )
