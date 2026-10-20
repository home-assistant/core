"""Constants for the counter integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import Counter

DOMAIN: Final = "counter"

DATA_COMPONENT: HassKey[EntityComponent[Counter]] = HassKey(DOMAIN)

VALUE: Final = "value"

SERVICE_DECREMENT: Final = "decrement"
SERVICE_INCREMENT: Final = "increment"
SERVICE_RESET: Final = "reset"
SERVICE_SET_VALUE: Final = "set_value"


class CounterEntityStateAttribute(StrEnum):
    """State attributes for counter entities."""

    EDITABLE = "editable"
    INITIAL = "initial"
    STEP = "step"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
