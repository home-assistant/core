"""Services for NINA."""

from enum import StrEnum

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import service

from .const import DOMAIN


class NinaService(StrEnum):
    """Store keys for NINA services."""

    GET_DETAILS = "get_details"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NinaService.GET_DETAILS,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=None,
        func="get_details",
        supports_response=SupportsResponse.ONLY,
    )
