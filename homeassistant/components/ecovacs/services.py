"""Ecovacs services."""

from homeassistant.components.lawn_mower import DOMAIN as LAWN_MOWER_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import service

from .const import DOMAIN

SERVICE_RAW_GET_POSITIONS = "raw_get_positions"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    # Vacuum Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RAW_GET_POSITIONS,
        entity_domain=VACUUM_DOMAIN,
        schema=None,
        func="async_raw_get_positions",
        supports_response=SupportsResponse.ONLY,
    )

    # Lawn Mower Services (Ecovacs GOAT family — same raw position payload as
    # vacuums; exposed here so users can capture the response and inspect
    # additional fields the cloud may return, e.g. RTK status / satellite count
    # for GOAT mowers).
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RAW_GET_POSITIONS,
        entity_domain=LAWN_MOWER_DOMAIN,
        schema=None,
        func="async_raw_get_positions",
        supports_response=SupportsResponse.ONLY,
    )
