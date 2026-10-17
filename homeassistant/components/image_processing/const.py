"""Constants for the image_processing component."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .entity import ImageProcessingEntity

DOMAIN: Final = "image_processing"

SERVICE_SCAN: Final = "scan"

EVENT_DETECT_FACE = "image_processing.detect_face"

ATTR_AGE = "age"
ATTR_CONFIDENCE: Final = "confidence"
ATTR_FACES = "faces"
ATTR_GENDER = "gender"
ATTR_GLASSES = "glasses"
ATTR_MOTION: Final = "motion"
ATTR_TOTAL_FACES = "total_faces"

CONF_CONFIDENCE = "confidence"

DEFAULT_TIMEOUT = 10
DEFAULT_CONFIDENCE = 80

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
