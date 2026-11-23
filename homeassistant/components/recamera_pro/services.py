"""Action registration for reCamera Pro."""

import probatio

from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import service

from .const import (
    ATTR_CAPTURE_OUTPUT,
    ATTR_RECORD_DURATION,
    DOMAIN,
    SERVICE_CAPTURE_DEVICE,
    SERVICE_RECORD_DEVICE,
    SERVICE_STOP_DEVICE_CAPTURE,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration actions before any config entry loads."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CAPTURE_DEVICE,
        entity_domain="camera",
        schema={probatio.Optional(ATTR_CAPTURE_OUTPUT): str},
        func="async_capture_device_snapshot",
        supports_response=SupportsResponse.OPTIONAL,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RECORD_DEVICE,
        entity_domain="camera",
        schema={
            probatio.Optional(ATTR_CAPTURE_OUTPUT): str,
            probatio.Optional(ATTR_RECORD_DURATION, default=30): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=3600)
            ),
        },
        func="async_start_device_recording",
        supports_response=SupportsResponse.OPTIONAL,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_STOP_DEVICE_CAPTURE,
        entity_domain="camera",
        schema=None,
        func="async_stop_device_capture",
        supports_response=SupportsResponse.OPTIONAL,
    )
