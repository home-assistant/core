"""Constants for the input_select integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import InputSelectData

DOMAIN: Final = "input_select"

DATA_INPUT_SELECT: HassKey[InputSelectData] = HassKey(DOMAIN)

SERVICE_SET_OPTIONS: Final = "set_options"


class InputSelectEntityStateAttribute(StrEnum):
    """State attributes for input select entities."""

    EDITABLE = "editable"
