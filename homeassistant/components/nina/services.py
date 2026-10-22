"""Services for NINA."""

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import service

from .const import DOMAIN, SERVICE_GET_DETAILS


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_DETAILS,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=None,
        func="get_details",
        supports_response=SupportsResponse.ONLY,
    )
