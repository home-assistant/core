"""Constants for the tolo integration."""

from enum import Enum

from tololib import AromaTherapySlot as ToloAromaTherapySlot, LampMode as ToloLampMode

DOMAIN = "tolo"
DEFAULT_NAME = "TOLO Sauna"

DEFAULT_RETRY_TIMEOUT = 1
DEFAULT_RETRY_COUNT = 3


class AromaTherapySlot(Enum):
    """Mapping to TOLO Aroma Therapy Slot."""

    A = ToloAromaTherapySlot.A
    B = ToloAromaTherapySlot.B


class LampMode(Enum):
    """Mapping to TOLO Lamp Mode."""

    MANUAL = ToloLampMode.MANUAL
    AUTOMATIC = ToloLampMode.AUTOMATIC
