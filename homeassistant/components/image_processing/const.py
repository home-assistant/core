"""Constants for the image_processing component."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import ImageProcessingEntity

DOMAIN: Final = "image_processing"

SERVICE_SCAN: Final = "scan"

DATA_COMPONENT: HassKey[EntityComponent[ImageProcessingEntity]] = HassKey(DOMAIN)


class ImageProcessingEntityStateAttribute(StrEnum):
    """State attributes for image processing entities."""

    FACES = "faces"
    TOTAL_FACES = "total_faces"


class ImageProcessingDeviceClass(StrEnum):
    """Device class for image processing entities."""

    # Automatic license plate recognition
    ALPR = "alpr"

    # Face
    FACE = "face"

    # OCR
    OCR = "ocr"
