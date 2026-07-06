"""Constants for the image integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import ImageEntity


class ImageEntityStateAttribute(StrEnum):
    """State attributes for image entities."""

    ACCESS_TOKEN = "access_token"


DOMAIN: Final = "image"
DATA_COMPONENT: HassKey[EntityComponent[ImageEntity]] = HassKey(DOMAIN)

IMAGE_TIMEOUT: Final = 10
