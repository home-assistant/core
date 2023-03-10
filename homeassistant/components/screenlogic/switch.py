"""Support for a ScreenLogic 'circuit' switch."""
import logging

from screenlogicpy.const import (
    CODE,
    DATA as SL_DATA,
    GENERIC_CIRCUIT_NAMES,
    INTERFACE_GROUP,
)

from homeassistant.components.switch import SwitchEntity
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
            ScreenLogicSwitch(
                coordinator,
                circuit_num,
                CODE.STATUS_CHANGED,
                circuit["name"] not in GENERIC_CIRCUIT_NAMES
                and circuit["interface"] != INTERFACE_GROUP.DONT_SHOW,
            )
            for circuit_num, circuit in circuits.items()
            if circuit["function"] not in LIGHT_CIRCUIT_FUNCTIONS
        ]
    )


class ScreenLogicSwitch(ScreenLogicCircuitEntity, SwitchEntity):
    """Class to represent a ScreenLogic Switch."""
