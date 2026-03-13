"""Services for NINA."""

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import service

from .const import (
    DOMAIN,
    SERVICE_GET_AFFECTED_AREAS,
    SERVICE_GET_DESCRIPTION,
    SERVICE_GET_RECOMMENDED_ACTIONS,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_DESCRIPTION,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=None,
        func="get_description",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_AFFECTED_AREAS,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=None,
        func="get_full_affected_areas",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_RECOMMENDED_ACTIONS,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=None,
        func="get_recommended_actions",
        supports_response=SupportsResponse.ONLY,
    )
