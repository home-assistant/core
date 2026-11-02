"""Constants for the input_number integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import InputNumberData

DOMAIN: Final = "input_number"

DATA_INPUT_NUMBER: HassKey[InputNumberData] = HassKey(DOMAIN)

ATTR_VALUE: Final = "value"

CONF_INITIAL = "initial"
CONF_MIN = "min"
CONF_MAX = "max"
CONF_STEP = "step"

SERVICE_SET_VALUE: Final = "set_value"
SERVICE_INCREMENT: Final = "increment"
SERVICE_DECREMENT: Final = "decrement"


class InputNumberEntityStateAttribute(StrEnum):
    """State attributes for input number entities."""

    INITIAL = "initial"
    EDITABLE = "editable"


class InputNumberService(StrEnum):
    """Store keys for input number services."""

    DECREMENT = "decrement"
    INCREMENT = "increment"
    RELOAD = "reload"
    SET_VALUE = "set_value"


class InputNumberServiceArgument(StrEnum):
    """Store keys for input number service arguments."""

    VALUE = "value"
