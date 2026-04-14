"""Support for interacting with Snapcast clients."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_SNAPSHOT = "snapshot"
SERVICE_RESTORE = "restore"
SERVICE_SET_LATENCY = "set_latency"

ATTR_LATENCY = "latency"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SNAPSHOT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_snapshot",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RESTORE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_restore",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_LATENCY,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={vol.Required(ATTR_LATENCY): cv.positive_int},
        func="async_set_latency",
    )
