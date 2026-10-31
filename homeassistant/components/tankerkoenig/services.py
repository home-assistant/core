"""Services for the Tankerkoenig integration."""

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import service

from .const import DOMAIN, SERVICE_GET_OPENING_TIMES


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Tankerkoenig integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_OPENING_TIMES,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=None,
        func="async_get_opening_times",
        supports_response=SupportsResponse.ONLY,
    )
