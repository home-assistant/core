"""Services for the EZVIZ integration."""

from enum import StrEnum

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN


class EzvizService(StrEnum):
    """Store keys for EZVIZ services."""

    WAKE_DEVICE = "wake_device"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the EZVIZ integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EzvizService.WAKE_DEVICE,
        entity_domain=CAMERA_DOMAIN,
        schema=None,
        func="perform_wake_device",
    )
