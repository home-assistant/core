"""Constants for the image_processing component."""

from enum import StrEnum


class ImageProcessingEntityStateAttribute(StrEnum):
    """State attributes for image processing entities."""

    FACES = "faces"
    TOTAL_FACES = "total_faces"
