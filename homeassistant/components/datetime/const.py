"""Provides the constants needed for the component."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import DateTimeEntity

DOMAIN: Final = "datetime"
DATA_COMPONENT: HassKey[EntityComponent[DateTimeEntity]] = HassKey(DOMAIN)

ATTR_DATETIME = "datetime"

SERVICE_SET_VALUE = "set_value"


class DateTimeService(StrEnum):
    """Store keys for datetime services."""

    SET_VALUE = "set_value"


class DateTimeServiceArgument(StrEnum):
    """Store keys for datetime service arguments."""

    DATETIME = "datetime"
