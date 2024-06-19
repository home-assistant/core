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
from .entity import (
    ScreenLogicCircuitEntity,
    ScreenLogicPushEntityDescription,
    ScreenLogicSwitchingEntity,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ScreenLogicCircuitSwitchDescription(
    SwitchEntityDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogic switch entity."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    entities: list[ScreenLogicSwitchingEntity] = []
    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[SL_DOMAIN][
        config_entry.entry_id
    ]
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
