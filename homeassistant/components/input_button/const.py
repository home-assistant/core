"""Constants for the input_button integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import InputButtonData

DOMAIN: Final = "input_button"

DATA_INPUT_BUTTON: HassKey[InputButtonData] = HassKey(DOMAIN)


class InputButtonService(StrEnum):
    """Store keys for input button services."""

    PRESS = "press"
    RELOAD = "reload"


class InputButtonEntityStateAttribute(StrEnum):
    """State attributes for input button entities."""

    EDITABLE = "editable"
