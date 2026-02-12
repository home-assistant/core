"""Shark IQ services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_ROOMS, DOMAIN

SERVICE_CLEAN_ROOM = "clean_room"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    # Vacuum Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAN_ROOM,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Required(ATTR_ROOMS): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
        },
        func="async_clean_room",
    )
