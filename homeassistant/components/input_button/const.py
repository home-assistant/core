"""Constants for the input_button integration."""

from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import InputButtonData

DOMAIN: Final = "input_button"

DATA_INPUT_BUTTON: HassKey[InputButtonData] = HassKey(DOMAIN)
