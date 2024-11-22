"""Support for a ScreenLogic 'circuit' switch."""

from dataclasses import dataclass

from screenlogicpy.const.data import ATTR, DEVICE
from screenlogicpy.const.msg import CODE
from screenlogicpy.device_const.circuit import GENERIC_CIRCUIT_NAMES, INTERFACE

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import LIGHT_CIRCUIT_FUNCTIONS
from .entity import (
    ScreenLogicCircuitEntity,
    ScreenLogicPushEntityDescription,
    ScreenLogicSwitchingEntity,
)
from .types import ScreenLogicConfigEntry


@dataclass(frozen=True, kw_only=True)
class ScreenLogicCircuitSwitchDescription(
    SwitchEntityDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogic switch entity."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ScreenLogicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    entities: list[ScreenLogicSwitchingEntity] = []
    coordinator = config_entry.runtime_data
    gateway = coordinator.gateway
    for circuit_index, circuit_data in gateway.get_data(DEVICE.CIRCUIT).items():
        if (
            not circuit_data
            or ((circuit_function := circuit_data.get(ATTR.FUNCTION)) is None)
            or circuit_function in LIGHT_CIRCUIT_FUNCTIONS
        ):
            continue
        circuit_name = circuit_data[ATTR.NAME]
        circuit_interface = INTERFACE(circuit_data[ATTR.INTERFACE])
        entities.append(
            ScreenLogicCircuitSwitch(
                coordinator,
                ScreenLogicCircuitSwitchDescription(
                    subscription_code=CODE.STATUS_CHANGED,
                    data_root=(DEVICE.CIRCUIT,),
                    key=circuit_index,
                    entity_registry_enabled_default=(
                        circuit_name not in GENERIC_CIRCUIT_NAMES
                        and circuit_interface != INTERFACE.DONT_SHOW
                    ),
                ),
            )
        )

    async_add_entities(entities)


class ScreenLogicCircuitSwitch(ScreenLogicCircuitEntity, SwitchEntity):
    """Class to represent a ScreenLogic Switch."""

    entity_description: ScreenLogicCircuitSwitchDescription
