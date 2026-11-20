"""Constants for the input_select integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import InputSelectData

DOMAIN: Final = "input_select"

DATA_INPUT_SELECT: HassKey[InputSelectData] = HassKey(DOMAIN)

SERVICE_SET_OPTIONS: Final = "set_options"

CONF_INITIAL = "initial"


class InputSelectEntityStateAttribute(StrEnum):
    """State attributes for input select entities."""

    EDITABLE = "editable"


class InputSelectService(StrEnum):
    """Store keys for input select services."""

    RELOAD = "reload"
    SELECT_FIRST = "select_first"
    SELECT_LAST = "select_last"
    SELECT_NEXT = "select_next"
    SELECT_OPTION = "select_option"
    SELECT_PREVIOUS = "select_previous"
    SET_OPTIONS = "set_options"


class InputSelectServiceArgument(StrEnum):
    """Store keys for input select service arguments."""

    CYCLE = "cycle"
    OPTION = "option"
    OPTIONS = "options"
