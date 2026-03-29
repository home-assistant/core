"""Support for Elgato services."""

from __future__ import annotations

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN

SERVICE_IDENTIFY = "identify"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_IDENTIFY,
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_identify",
    )
