"""Collection image services."""

import voluptuous as vol

from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

SERVICE_SHUFFLE = "shuffle"
SERVICE_SELECT_FIRST = "select_first"
SERVICE_SELECT_LAST = "select_last"
SERVICE_SELECT_NEXT = "select_next"
SERVICE_SELECT_PREVIOUS = "select_previous"
ATTR_WRAP = "wrap"


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
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SELECT_FIRST,
        entity_domain=IMAGE_DOMAIN,
        schema={},
        func="get_first_image",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SELECT_LAST,
        entity_domain=IMAGE_DOMAIN,
        schema={},
        func="get_last_image",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SELECT_NEXT,
        entity_domain=IMAGE_DOMAIN,
        schema={vol.Optional(ATTR_WRAP): cv.boolean},
        func="get_next_image",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SELECT_PREVIOUS,
        entity_domain=IMAGE_DOMAIN,
        schema={vol.Optional(ATTR_WRAP): cv.boolean},
        func="get_previous_image",
    )
