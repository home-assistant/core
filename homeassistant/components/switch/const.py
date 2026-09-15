"""Constants for the Switch integration."""

from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import SwitchEntity


DOMAIN: Final = "switch"
DATA_COMPONENT: HassKey[EntityComponent[SwitchEntity]] = HassKey(DOMAIN)
