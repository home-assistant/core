"""Services for the EnergyID integration."""

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import service

from .const import DOMAIN

SERVICE_GET_DIRECTIVE_SCHEDULE = "get_directive_schedule"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the EnergyID actions."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_DIRECTIVE_SCHEDULE,
        entity_domain=SENSOR_DOMAIN,
        schema=None,
        func="async_get_directive_schedule",
        supports_response=SupportsResponse.ONLY,
    )
