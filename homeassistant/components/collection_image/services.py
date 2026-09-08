"""Collection image services."""

from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN

SERVICE_SHUFFLE = "shuffle"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Collection image services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SHUFFLE,
        entity_domain=IMAGE_DOMAIN,
        schema={},
        func="get_random_image",
    )
