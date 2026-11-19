"""Provides the constants needed for the component."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import DateEntity

DOMAIN: Final = "date"
DATA_COMPONENT: HassKey[EntityComponent[DateEntity]] = HassKey(DOMAIN)

SERVICE_SET_VALUE = "set_value"


class DateService(StrEnum):
    """Store keys for date services."""

    SET_VALUE = "set_value"


class DateServiceArgument(StrEnum):
    """Store keys for date service arguments."""

    DATE = "date"
