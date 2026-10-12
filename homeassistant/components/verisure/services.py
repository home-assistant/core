"""Services for the Verisure integration."""

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import (
    DOMAIN,
    SERVICE_CAPTURE_SMARTCAM,
    SERVICE_DISABLE_AUTOLOCK,
    SERVICE_ENABLE_AUTOLOCK,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Verisure integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CAPTURE_SMARTCAM,
        entity_domain=CAMERA_DOMAIN,
        schema=None,
        func="capture_smartcam",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DISABLE_AUTOLOCK,
        entity_domain=LOCK_DOMAIN,
        schema=None,
        func="disable_autolock",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ENABLE_AUTOLOCK,
        entity_domain=LOCK_DOMAIN,
        schema=None,
        func="enable_autolock",
    )
