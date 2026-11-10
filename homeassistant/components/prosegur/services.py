"""Services for the Prosegur Alarm integration."""

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN, SERVICE_REQUEST_IMAGE


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Prosegur Alarm integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_REQUEST_IMAGE,
        entity_domain=CAMERA_DOMAIN,
        schema=None,
        func="async_request_image",
    )
