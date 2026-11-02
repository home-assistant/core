"""Constants for the hddtemp integration."""

from enum import StrEnum


class HddtempEntityStateAttribute(StrEnum):
    """State attributes for hddtemp entities."""

    DEVICE = "device"
    MODEL = "model"
