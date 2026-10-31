"""Constants for the input_boolean integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import InputBooleanData

DOMAIN: Final = "input_boolean"

CONF_INITIAL = "initial"

DATA_INPUT_BOOLEAN: HassKey[InputBooleanData] = HassKey(DOMAIN)


class InputBooleanEntityStateAttribute(StrEnum):
    """State attributes for input boolean entities."""

    EDITABLE = "editable"


class InputBooleanService(StrEnum):
    """Store keys for input boolean services."""

    RELOAD = "reload"
    TOGGLE = "toggle"
    TURN_OFF = "turn_off"
    TURN_ON = "turn_on"
