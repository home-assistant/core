"""Constants for the input_datetime component."""

import datetime as dt
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import InputDatetimeData

DOMAIN: Final = "input_datetime"

DATA_INPUT_DATETIME: HassKey[InputDatetimeData] = HassKey(DOMAIN)


CONF_HAS_DATE = "has_date"
CONF_HAS_TIME = "has_time"
CONF_INITIAL = "initial"

DEFAULT_TIME = dt.time(0, 0, 0)


FMT_DATE = "%Y-%m-%d"
FMT_TIME = "%H:%M:%S"
FMT_DATETIME = f"{FMT_DATE} {FMT_TIME}"


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


class InputDatetimeService(StrEnum):
    """Store keys for input datetime services."""

    RELOAD = "reload"
    SET = "set_datetime"


class InputDatetimeServiceArgument(StrEnum):
    """Store keys for input datetime service arguments."""

    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"
    TIMESTAMP = "timestamp"
