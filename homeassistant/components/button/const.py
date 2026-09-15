"""Provides the constants needed for the component."""

from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import ButtonEntity

DOMAIN: Final = "button"
DATA_COMPONENT: HassKey[EntityComponent[ButtonEntity]] = HassKey(DOMAIN)

SERVICE_PRESS = "press"
