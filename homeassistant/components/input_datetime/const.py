"""Constants for the input_datetime component."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import InputDatetimeData

DOMAIN: Final = "input_datetime"

DATA_INPUT_DATETIME: HassKey[InputDatetimeData] = HassKey(DOMAIN)

ATTR_DATETIME: Final = "datetime"
ATTR_TIMESTAMP: Final = "timestamp"


class InputDatetimeEntityCapabilityAttribute(StrEnum):
    """Capability attributes for input datetime entities."""

    HAS_DATE = "has_date"
    HAS_TIME = "has_time"


class InputDatetimeEntityStateAttribute(StrEnum):
    """State attributes for input datetime entities."""

    EDITABLE = "editable"
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"
    MINUTE = "minute"
    SECOND = "second"
    TIMESTAMP = "timestamp"
