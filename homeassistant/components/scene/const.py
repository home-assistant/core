"""Constants for the scene integration."""

from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import BaseScene

DOMAIN: Final = "scene"
DATA_COMPONENT: HassKey[EntityComponent[BaseScene]] = HassKey(DOMAIN)
