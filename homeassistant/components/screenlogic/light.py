"""Support for a ScreenLogic light 'circuit' switch."""
import logging

from screenlogicpy.const import CODE, DATA as SL_DATA, GENERIC_CIRCUIT_NAMES

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ScreenlogicDataUpdateCoordinator
from .const import DOMAIN, LIGHT_CIRCUIT_FUNCTIONS
from .entity import ScreenLogicCircuitEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    circuits = coordinator.gateway_data[SL_DATA.KEY_CIRCUITS]
    async_add_entities(
        [
            ScreenLogicLight(
                coordinator,
                circuit_num,
                CODE.STATUS_CHANGED,
                circuit["name"] not in GENERIC_CIRCUIT_NAMES,
            )
            for circuit_num, circuit in circuits.items()
            if circuit["function"] in LIGHT_CIRCUIT_FUNCTIONS
        ]
    )


class ScreenLogicLight(ScreenLogicCircuitEntity, LightEntity):
    """Class to represent a ScreenLogic Light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
