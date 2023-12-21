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


@dataclass(frozen=True)
class ScreenLogicCircuitSwitchDescription(
    SwitchEntityDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogic switch entity."""


@dataclass(frozen=True)
class ScreenLogicSCGSwitchDescription(
    SwitchEntityDescription, ScreenLogicEntityDescription
):
    """Describes a ScreenLogic switch entity."""


SUPPORTED_SCG_SWITCHES = [
    ScreenLogicSCGSwitchDescription(
        data_root=(DEVICE.SCG,),
        key=VALUE.SUPER_CHLORINATE,
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        enabled_lambda=lambda equipment_flags: EQUIPMENT_FLAG.INTELLICHEM
        not in equipment_flags,
    ),
]


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

    scg_switch_description: ScreenLogicSCGSwitchDescription
    for scg_switch_description in SUPPORTED_SCG_SWITCHES:
        scg_switch_data_path = (
            *scg_switch_description.data_root,
            scg_switch_description.key,
        )
        if EQUIPMENT_FLAG.CHLORINATOR not in gateway.equipment_flags:
            cleanup_excluded_entity(coordinator, DOMAIN, scg_switch_data_path)
        else:
            entities.append(ScreenLogicSCGSwitch(coordinator, scg_switch_description))
    async_add_entities(entities)


class ScreenLogicCircuitSwitch(
    ScreenLogicCircuitEntity, ScreenLogicPushEntity, SwitchEntity
):
    """Class to represent a ScreenLogic Switch."""

    entity_description: ScreenLogicCircuitSwitchDescription


class ScreenLogicSCGSwitch(ScreenLogicCircuitEntity, SwitchEntity):
    """Class for ScreenLogic SCG switch."""

    entity_description: ScreenLogicSCGSwitchDescription

    def __init__(
        self,
        coordinator: ScreenlogicDataUpdateCoordinator,
        entity_description: ScreenLogicSCGSwitchDescription,
    ) -> None:
        """Initialize of the entity."""
        super().__init__(coordinator, entity_description)
        if entity_description.enabled_lambda:
            self._attr_entity_registry_enabled_default = (
                entity_description.enabled_lambda(coordinator.gateway.equipment_flags)
            )

    async def _async_set_state(self, state: ON_OFF) -> None:
        try:
            await self.gateway.async_set_scg_config(**{self._data_key: state.value})
        except (ScreenLogicCommunicationError, ScreenLogicError) as sle:
            raise HomeAssistantError(
                f"Failed to set_scg_config {self._data_key} {state.value}: {sle.msg}"
            ) from sle
        _LOGGER.debug("Set scg config %s %s", self._data_key, state.value)
        await self._async_refresh()
