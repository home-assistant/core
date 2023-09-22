"""Support for a ScreenLogic 'circuit' switch."""
from dataclasses import dataclass
import logging

from screenlogicpy.const.data import ATTR, DEVICE
from screenlogicpy.const.msg import CODE
from screenlogicpy.device_const.circuit import GENERIC_CIRCUIT_NAMES, INTERFACE

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as SL_DOMAIN, LIGHT_CIRCUIT_FUNCTIONS
from .coordinator import ScreenlogicDataUpdateCoordinator
from .entity import ScreenLogicCircuitEntity, ScreenLogicPushEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    entities: list[ScreenLogicSwitch] = []
    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[SL_DOMAIN][
        config_entry.entry_id
    ]
    gateway = coordinator.gateway
    for circuit_index, circuit_data in gateway.get_data(DEVICE.CIRCUIT).items():
        if circuit_data[ATTR.FUNCTION] in LIGHT_CIRCUIT_FUNCTIONS:
            continue
        circuit_name = circuit_data[ATTR.NAME]
        circuit_interface = INTERFACE(circuit_data[ATTR.INTERFACE])
        entities.append(
            ScreenLogicSwitch(
                coordinator,
                ScreenLogicSwitchDescription(
                    subscription_code=CODE.STATUS_CHANGED,
                    data_path=(DEVICE.CIRCUIT, circuit_index),
                    key=circuit_index,
                    name=circuit_name,
                    entity_registry_enabled_default=(
                        circuit_name not in GENERIC_CIRCUIT_NAMES
                        and circuit_interface != INTERFACE.DONT_SHOW
                    ),
                ),
            )
        )

    async_add_entities(entities)


@dataclass
class ScreenLogicSwitchDescription(
    SwitchEntityDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogic switch entity."""


class ScreenLogicSwitch(ScreenLogicCircuitEntity, SwitchEntity):
    """Class to represent a ScreenLogic Switch."""

    entity_description: ScreenLogicSwitchDescription
