"""Provides the constants needed for the component."""

from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import DateEntity

DOMAIN: Final = "date"
DATA_COMPONENT: HassKey[EntityComponent[DateEntity]] = HassKey(DOMAIN)

SERVICE_SET_VALUE = "set_value"
