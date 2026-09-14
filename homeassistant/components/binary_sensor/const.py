"""Constants for the binary_sensor integration."""

from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import BinarySensorEntity


DOMAIN: Final = "binary_sensor"

DATA_COMPONENT: HassKey[EntityComponent[BinarySensorEntity]] = HassKey(DOMAIN)
