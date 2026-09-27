"""Provides the constants needed for the component."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import SelectEntity

DOMAIN: Final = "select"
DATA_COMPONENT: HassKey[EntityComponent[SelectEntity]] = HassKey(DOMAIN)


class SelectEntityCapabilityAttribute(StrEnum):
    """Capability attributes for select entities."""

    OPTIONS = "options"


ATTR_CYCLE = "cycle"
ATTR_OPTIONS = "options"

CONF_CYCLE = "cycle"
CONF_OPTION = "option"

SERVICE_SELECT_FIRST = "select_first"
SERVICE_SELECT_LAST = "select_last"
SERVICE_SELECT_NEXT = "select_next"
SERVICE_SELECT_PREVIOUS = "select_previous"
