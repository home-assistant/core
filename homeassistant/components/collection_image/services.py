"""Collection image services."""

from enum import StrEnum

import probatio

from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import MediaSelector

from .const import DOMAIN


class CollectionImageService(StrEnum):
    """Store keys for Collection image services."""

    SHUFFLE = "shuffle"
    SELECT_FIRST = "select_first"
    SELECT_LAST = "select_last"
    SELECT_NEXT = "select_next"
    SELECT_PREVIOUS = "select_previous"
    SELECT_IMAGE = "select_image"


class CollectionImageServiceArgument(StrEnum):
    """Store keys for Collection image service arguments."""

    WRAP = "wrap"
    IMAGE = "image"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Collection image services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        CollectionImageService.SHUFFLE,
        entity_domain=IMAGE_DOMAIN,
        schema={},
        func="get_random_image",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        CollectionImageService.SELECT_FIRST,
        entity_domain=IMAGE_DOMAIN,
        schema={},
        func="get_first_image",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        CollectionImageService.SELECT_LAST,
        entity_domain=IMAGE_DOMAIN,
        schema={},
        func="get_last_image",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        CollectionImageService.SELECT_NEXT,
        entity_domain=IMAGE_DOMAIN,
        schema={probatio.Optional(CollectionImageServiceArgument.WRAP): cv.boolean},
        func="get_next_image",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        CollectionImageService.SELECT_PREVIOUS,
        entity_domain=IMAGE_DOMAIN,
        schema={probatio.Optional(CollectionImageServiceArgument.WRAP): cv.boolean},
        func="get_previous_image",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        CollectionImageService.SELECT_IMAGE,
        entity_domain=IMAGE_DOMAIN,
        schema={
            probatio.Required(CollectionImageServiceArgument.IMAGE): MediaSelector(
                {"accept": ["image/*"]}
            )
        },
        func="select_image",
    )
