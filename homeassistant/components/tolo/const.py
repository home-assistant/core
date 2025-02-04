"""Constants for the tolo integration."""

from enum import Enum

from tololib import AromaTherapySlot as ToloAromaTherapySlot, LampMode as ToloLampMode

DOMAIN = "tolo"
DEFAULT_NAME = "TOLO Steam Bath"

DEFAULT_RETRY_TIMEOUT = 1
DEFAULT_RETRY_COUNT = 3

CONF_ACCESSORIES = "accessories"
CONF_ACCESSORY_FAN = "fan"
CONF_ACCESSORY_LIGHT = "light"
CONF_ACCESSORY_SALT_BATH = "salt_bath"
CONF_ACCESSORY_AROMA_THERAPY = "aroma_therapy"
CONF_ACCESSORY_AROMA_THERAPY_TYPE = "aroma_therapy_type"
CONF_EXPERT = "expert"
CONF_RETRY_TIMEOUT = "retry_timeout"
CONF_RETRY_COUNT = "retry_count"


class AromaTherapySlot(Enum):
    """Mapping to TOLO Aroma Therapy Slot."""

    A = ToloAromaTherapySlot.A
    B = ToloAromaTherapySlot.B


class LampMode(Enum):
    """Mapping to TOLO Lamp Mode."""

    MANUAL = ToloLampMode.MANUAL
    AUTOMATIC = ToloLampMode.AUTOMATIC
