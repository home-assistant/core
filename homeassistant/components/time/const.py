"""Provides the constants needed for the component."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import TimeEntity

DOMAIN: Final = "time"
DATA_COMPONENT: HassKey[EntityComponent[TimeEntity]] = HassKey(DOMAIN)

SERVICE_SET_VALUE = "set_value"


class TimeService(StrEnum):
    """Store keys for time services."""

    SET_VALUE = "set_value"


class TimeServiceArgument(StrEnum):
    """Store keys for time service arguments."""

    TIME = "time"
