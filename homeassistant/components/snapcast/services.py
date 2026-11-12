"""Support for interacting with Snapcast clients."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class SnapcastService(StrEnum):
    """Store keys for Snapcast services."""

    SNAPSHOT = "snapshot"
    RESTORE = "restore"
    SET_LATENCY = "set_latency"


class SnapcastServiceArgument(StrEnum):
    """Store keys for Snapcast service arguments."""

    LATENCY = "latency"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SnapcastService.SNAPSHOT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_snapshot",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SnapcastService.RESTORE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_restore",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SnapcastService.SET_LATENCY,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={probatio.Required(SnapcastServiceArgument.LATENCY): cv.positive_int},
        func="async_set_latency",
    )
