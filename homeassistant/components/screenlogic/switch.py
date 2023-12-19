"""Support for a ScreenLogic 'circuit' switch."""
from dataclasses import dataclass
import logging

from screenlogicpy.const.common import (
    ON_OFF,
    ScreenLogicCommunicationError,
    ScreenLogicError,
)
from screenlogicpy.const.data import ATTR, DEVICE, VALUE
from screenlogicpy.const.msg import CODE
from screenlogicpy.device_const.circuit import GENERIC_CIRCUIT_NAMES, INTERFACE
from screenlogicpy.device_const.system import EQUIPMENT_FLAG

from homeassistant.components.switch import (
    DOMAIN,
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as SL_DOMAIN, LIGHT_CIRCUIT_FUNCTIONS
from .coordinator import ScreenlogicDataUpdateCoordinator
from .entity import (
    ScreenLogicCircuitEntity,
    ScreenLogicEntityDescription,
    ScreenLogicPushEntity,
    ScreenLogicPushEntityDescription,
)
from .util import cleanup_excluded_entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    entities: list[ScreenLogicCircuitEntity] = []
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
    super_chlor_data_root = (DEVICE.SCG,)
    super_chlor_key = VALUE.SUPER_CHLORINATE
    super_chlor_data_path = (*super_chlor_data_root, super_chlor_key)
    if EQUIPMENT_FLAG.CHLORINATOR not in gateway.equipment_flags:
        cleanup_excluded_entity(coordinator, DOMAIN, super_chlor_data_path)
    else:
        entities.append(
            ScreenLogicSCGSwitchEntity(
                coordinator,
                ScreenLogicSCGSwitchDescription(
                    data_root=super_chlor_data_root,
                    key=super_chlor_key,
                    device_class=SwitchDeviceClass.SWITCH,
                    entity_category=EntityCategory.CONFIG,
                ),
            )
        )
    async_add_entities(entities)


@dataclass(frozen=True)
class ScreenLogicCircuitSwitchDescription(
    SwitchEntityDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogic switch entity."""


class ScreenLogicCircuitSwitch(
    ScreenLogicCircuitEntity, ScreenLogicPushEntity, SwitchEntity
):
    """Class to represent a ScreenLogic Switch."""

    entity_description: ScreenLogicCircuitSwitchDescription


@dataclass(frozen=True)
class ScreenLogicSCGSwitchDescription(
    SwitchEntityDescription, ScreenLogicEntityDescription
):
    """Describes a ScreenLogic switch entity."""


class ScreenLogicSCGSwitchEntity(ScreenLogicCircuitEntity, SwitchEntity):
    """Class for ScreenLogic super chlorination switch."""

    entity_description: ScreenLogicSCGSwitchDescription

    async def _async_set_state(self, state: ON_OFF) -> None:
        try:
            await self.gateway.async_set_scg_config(
                **{VALUE.SUPER_CHLORINATE: state.value}
            )
        except (ScreenLogicCommunicationError, ScreenLogicError) as sle:
            raise HomeAssistantError(
                f"Failed to set_scg_config {self._data_key} {state.value}: {sle.msg}"
            ) from sle
        _LOGGER.debug("Set scg config %s %s", self._data_key, state.value)
