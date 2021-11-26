"""Support for a ScreenLogic 'circuit' switch."""
import logging

from screenlogicpy.const import DATA as SL_DATA, GENERIC_CIRCUIT_NAMES

from homeassistant.components.switch import SwitchEntity

from . import ScreenLogicCircuitEntity
from .const import DOMAIN, LIGHT_CIRCUIT_FUNCTIONS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            ScreenLogicSwitch(
                coordinator, circuit_num, circuit["name"] not in GENERIC_CIRCUIT_NAMES
            )
            for circuit_num, circuit in coordinator.data[SL_DATA.KEY_CIRCUITS].items()
            if circuit["function"] not in LIGHT_CIRCUIT_FUNCTIONS
        ]
    )


class ScreenLogicSwitch(ScreenLogicCircuitEntity, SwitchEntity):
    """Class to represent a ScreenLogic Switch."""
