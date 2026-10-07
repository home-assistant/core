"""Services for the EZVIZ integration."""

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN, SERVICE_WAKE_DEVICE


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the EZVIZ integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_WAKE_DEVICE,
        entity_domain=CAMERA_DOMAIN,
        schema=None,
        func="perform_wake_device",
    )
