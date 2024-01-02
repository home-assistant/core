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

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, NumberEntity
from homeassistant.components.switch import (
    DOMAIN,
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
    ScreenLogicPushEntityDescription,
    ScreenLogicSwitchingEntity,
)
from .util import cleanup_excluded_entity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScreenLogicSwitchDescription(
    SwitchEntityDescription, ScreenLogicEntityDescription
):
    """Describes a ScreenLogic switch entity."""


@dataclass(frozen=True)
class ScreenLogicCircuitSwitchDescription(
    SwitchEntityDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogic circuit switch entity."""


SUPPORTED_SUPER_CHLOR_SWITCHES = [
    ScreenLogicSwitchDescription(
        data_root=(DEVICE.SCG,),
        key=VALUE.SUPER_CHLORINATE,
        entity_category=EntityCategory.CONFIG,
    )
]


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
    for scg_super_chlor_switch_description in SUPPORTED_SUPER_CHLOR_SWITCHES:
        sup_chlor_switch_data_path = (
            *scg_super_chlor_switch_description.data_root,
            scg_super_chlor_switch_description.key,
        )
        if EQUIPMENT_FLAG.CHLORINATOR not in gateway.equipment_flags:
            cleanup_excluded_entity(coordinator, DOMAIN, sup_chlor_switch_data_path)
            continue
        if gateway.get_data(*sup_chlor_switch_data_path):
            entities.append(
                ScreenLogicSuperChlorinateSwitch(
                    coordinator, scg_super_chlor_switch_description
                )
            )

    async_add_entities(entities)


class ScreenLogicCircuitSwitch(ScreenLogicCircuitEntity, SwitchEntity):
    """Class to represent a ScreenLogic Switch."""

    entity_description: ScreenLogicCircuitSwitchDescription


class ScreenLogicSuperChlorinateSwitch(ScreenLogicSwitchingEntity, SwitchEntity):
    """Class to represent a ScreenLogic Super Chlorination switch."""

    entity_description: ScreenLogicSwitchDescription

    def __init__(
        self,
        coordinator: ScreenlogicDataUpdateCoordinator,
        entity_description: ScreenLogicSwitchDescription,
    ) -> None:
        """Initialize a ScreenLogic Super Chlorinate switch entity."""
        super().__init__(coordinator, entity_description)
        if entity_description.enabled_lambda:
            self._attr_entity_registry_enabled_default = (
                entity_description.enabled_lambda(coordinator.gateway.equipment_flags)
            )
        coordinator.super_chlor_entities[DOMAIN] = self

    async def _async_set_state(self, state: ON_OFF) -> None:
        runtime = None
        sc_number: NumberEntity | None = self.coordinator.super_chlor_entities.get(
            NUMBER_DOMAIN
        )
        if sc_number is not None and sc_number.native_value is not None:
            runtime = int(sc_number.native_value)

        try:
            await self.gateway.async_set_scg_config(
                super_chlorinate=state.value, super_chlor_timer=runtime
            )
        except (ScreenLogicCommunicationError, ScreenLogicError) as sle:
            raise HomeAssistantError(
                f"Failed to set '{self._data_key}' to {state.value}: {sle.msg}"
            ) from sle
        _LOGGER.debug("Set '%s' to %s", self._data_key, state.value)
        await self._async_refresh()
