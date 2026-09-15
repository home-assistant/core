"""Constants for the image_processing component."""

from enum import StrEnum
from typing import Final

DOMAIN: Final = "image_processing"


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
