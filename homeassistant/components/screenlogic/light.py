"""Support for a ScreenLogic light 'circuit' switch."""
import logging

from screenlogicpy.const import DATA as SL_DATA, GENERIC_CIRCUIT_NAMES

from homeassistant.components.light import LightEntity

from . import ScreenLogicCircuitEntity
from .const import DOMAIN, LIGHT_CIRCUIT_FUNCTIONS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            ScreenLogicLight(
                coordinator, circuit_num, circuit["name"] not in GENERIC_CIRCUIT_NAMES
            )
            for circuit_num, circuit in coordinator.data[SL_DATA.KEY_CIRCUITS].items()
            if circuit["function"] in LIGHT_CIRCUIT_FUNCTIONS
        ]
    )


class ScreenLogicLight(ScreenLogicCircuitEntity, LightEntity):
    """Class to represent a ScreenLogic Light."""
