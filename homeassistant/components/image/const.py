"""Constants for the image integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .entity import ImageEntity


class ImageEntityStateAttribute(StrEnum):
    """State attributes for image entities."""

    ACCESS_TOKEN = "access_token"


DOMAIN: Final = "image"

ATTR_FILENAME: Final = "filename"
SERVICE_SNAPSHOT: Final = "snapshot"
DATA_COMPONENT: HassKey[EntityComponent[ImageEntity]] = HassKey(DOMAIN)

IMAGE_TIMEOUT: Final = 10

DEFAULT_CONTENT_TYPE: Final = "image/jpeg"
ENTITY_IMAGE_URL: Final = "/api/image_proxy/{0}?token={1}"
GET_IMAGE_TIMEOUT: Final = 10

MAP_MAGIC_NUMBERS_TO_CONTENT_TYPE = {
    b"\x89PNG": "image/png",
    b"GIF8": "image/gif",
    b"RIFF": "image/webp",
    b"\x49\x49\x2a\x00": "image/tiff",
    b"\x4d\x4d\x00\x2a": "image/tiff",
    b"\xff\xd8\xff\xdb": "image/jpeg",
    b"\xff\xd8\xff\xe0": "image/jpeg",
    b"\xff\xd8\xff\xed": "image/jpeg",
    b"\xff\xd8\xff\xee": "image/jpeg",
    b"\xff\xd8\xff\xe1": "image/jpeg",
    b"\xff\xd8\xff\xe2": "image/jpeg",
}
