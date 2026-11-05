"""Constants for the input_text integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import InputTextData

DOMAIN: Final = "input_text"

DATA_INPUT_TEXT: HassKey[InputTextData] = HassKey(DOMAIN)

CONF_VALUE: Final = "value"
ATTR_VALUE: Final = CONF_VALUE
SERVICE_SET_VALUE: Final = "set_value"

CONF_INITIAL = "initial"
CONF_MIN = "min"
CONF_MAX = "max"
CONF_PATTERN = "pattern"


class InputTextEntityStateAttribute(StrEnum):
    """State attributes for input text entities."""

    EDITABLE = "editable"


class InputTextService(StrEnum):
    """Store keys for input text services."""

    RELOAD = "reload"
    SET_VALUE = "set_value"


class InputTextServiceArgument(StrEnum):
    """Store keys for input text service arguments."""

    VALUE = "value"
