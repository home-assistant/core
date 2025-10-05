"""Switch for Shelly."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from aioshelly.block_device import Block
from aioshelly.const import RPC_GENERATIONS

from homeassistant.components.climate import DOMAIN as CLIMATE_PLATFORM
from homeassistant.components.switch import (
    DOMAIN as SWITCH_PLATFORM,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    MODEL_FRANKEVER_IRRIGATION_CONTROLLER,
    MODEL_LINKEDGO_ST802_THERMOSTAT,
    MODEL_LINKEDGO_ST1820_THERMOSTAT,
    MODEL_NEO_WATER_VALVE,
    MODEL_TOP_EV_CHARGER_EVE01,
)
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    BlockEntityDescription,
    RpcEntityDescription,
    ShellyBlockAttributeEntity,
    ShellyRpcAttributeEntity,
    ShellySleepingBlockAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rpc,
    rpc_call,
)
from .utils import (
    async_remove_orphaned_entities,
    get_device_entry_gen,
    get_virtual_component_ids,
    is_block_exclude_from_relay,
    is_rpc_exclude_from_relay,
    is_view_for_platform,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BlockSwitchDescription(BlockEntityDescription, SwitchEntityDescription):
    """Class to describe a BLOCK switch."""


BLOCK_RELAY_SWITCHES = {
    ("relay", "output"): BlockSwitchDescription(
        key="relay|output",
        removal_condition=is_block_exclude_from_relay,
    )
}

BLOCK_SLEEPING_MOTION_SWITCH = {
    ("sensor", "motionActive"): BlockSwitchDescription(
        key="sensor|motionActive",
        name="Motion detection",
        entity_category=EntityCategory.CONFIG,
    )
}


@dataclass(frozen=True, kw_only=True)
class RpcSwitchDescription(RpcEntityDescription, SwitchEntityDescription):
    """Class to describe a RPC virtual switch."""

    is_on: Callable[[dict[str, Any]], bool]
    method_on: str
    method_off: str
    method_params_fn: Callable[[int | None, bool], dict]


RPC_RELAY_SWITCHES = {
    "switch": RpcSwitchDescription(
        key="switch",
        sub_key="output",
        removal_condition=is_rpc_exclude_from_relay,
        is_on=lambda status: bool(status["output"]),
        method_on="switch_set",
        method_off="switch_set",
        method_params_fn=lambda id, value: {"id": id, "on": value},
    ),
}

RPC_SWITCHES = {
    "boolean_generic": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        removal_condition=lambda config, _status, key: not is_view_for_platform(
            config, key, SWITCH_PLATFORM
        ),
        is_on=lambda status: bool(status["value"]),
        method_on="boolean_set",
        method_off="boolean_set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
        role="generic",
    ),
    "boolean_anti_freeze": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        entity_registry_enabled_default=False,
        is_on=lambda status: bool(status["value"]),
        method_on="Boolean.Set",
        method_off="Boolean.Set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
        role="anti_freeze",
        models={MODEL_LINKEDGO_ST802_THERMOSTAT, MODEL_LINKEDGO_ST1820_THERMOSTAT},
    ),
    "boolean_child_lock": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        is_on=lambda status: bool(status["value"]),
        method_on="Boolean.Set",
        method_off="Boolean.Set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
        role="child_lock",
        models={MODEL_LINKEDGO_ST1820_THERMOSTAT},
    ),
    "boolean_enable": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        entity_registry_enabled_default=False,
        is_on=lambda status: bool(status["value"]),
        method_on="Boolean.Set",
        method_off="Boolean.Set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
        role="enable",
        models={MODEL_LINKEDGO_ST802_THERMOSTAT, MODEL_LINKEDGO_ST1820_THERMOSTAT},
    ),
    "boolean_start_charging": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        is_on=lambda status: bool(status["value"]),
        method_on="Boolean.Set",
        method_off="Boolean.Set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
        role="start_charging",
        models={MODEL_TOP_EV_CHARGER_EVE01},
    ),
    "boolean_state": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        entity_registry_enabled_default=False,
        is_on=lambda status: bool(status["value"]),
        method_on="Boolean.Set",
        method_off="Boolean.Set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
        role="state",
        models={MODEL_NEO_WATER_VALVE},
    ),
    "boolean_zone0": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        is_on=lambda status: bool(status["value"]),
        method_on="Boolean.Set",
        method_off="Boolean.Set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
        role="zone0",
        models={MODEL_FRANKEVER_IRRIGATION_CONTROLLER},
    ),
    "boolean_zone1": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        is_on=lambda status: bool(status["value"]),
        method_on="Boolean.Set",
        method_off="Boolean.Set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
        role="zone1",
        models={MODEL_FRANKEVER_IRRIGATION_CONTROLLER},
    ),
    "boolean_zone2": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        is_on=lambda status: bool(status["value"]),
        method_on="Boolean.Set",
        method_off="Boolean.Set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
        role="zone2",
        models={MODEL_FRANKEVER_IRRIGATION_CONTROLLER},
    ),
    "boolean_zone3": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        is_on=lambda status: bool(status["value"]),
        method_on="Boolean.Set",
        method_off="Boolean.Set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
        role="zone3",
        models={MODEL_FRANKEVER_IRRIGATION_CONTROLLER},
    ),
    "boolean_zone4": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        is_on=lambda status: bool(status["value"]),
        method_on="Boolean.Set",
        method_off="Boolean.Set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
        role="zone4",
        models={MODEL_FRANKEVER_IRRIGATION_CONTROLLER},
    ),
    "boolean_zone5": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        is_on=lambda status: bool(status["value"]),
        method_on="Boolean.Set",
        method_off="Boolean.Set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
        role="zone5",
        models={MODEL_FRANKEVER_IRRIGATION_CONTROLLER},
    ),
    "script": RpcSwitchDescription(
        key="script",
        sub_key="running",
        is_on=lambda status: bool(status["running"]),
        method_on="script_start",
        method_off="script_stop",
        method_params_fn=lambda id, _: {"script_id": id},
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches for device."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        return async_setup_rpc_entry(hass, config_entry, async_add_entities)

    return async_setup_block_entry(hass, config_entry, async_add_entities)


@callback
def async_setup_block_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for block device."""
    coordinator = config_entry.runtime_data.block
    assert coordinator

    async_setup_entry_attribute_entities(
        hass, config_entry, async_add_entities, BLOCK_RELAY_SWITCHES, BlockRelaySwitch
    )

    async_setup_entry_attribute_entities(
        hass,
        config_entry,
        async_add_entities,
        BLOCK_SLEEPING_MOTION_SWITCH,
        BlockSleepingMotionSwitch,
    )


@callback
def async_setup_rpc_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    coordinator = config_entry.runtime_data.rpc
    assert coordinator

    async_setup_entry_rpc(
        hass, config_entry, async_add_entities, RPC_RELAY_SWITCHES, RpcRelaySwitch
    )

    async_setup_entry_rpc(
        hass, config_entry, async_add_entities, RPC_SWITCHES, RpcSwitch
    )

    # the user can remove virtual components from the device configuration, so we need
    # to remove orphaned entities
    virtual_switch_ids = get_virtual_component_ids(
        coordinator.device.config, SWITCH_PLATFORM
    )
    async_remove_orphaned_entities(
        hass,
        config_entry.entry_id,
        coordinator.mac,
        SWITCH_PLATFORM,
        virtual_switch_ids,
        "boolean",
    )

    # if the script is removed, from the device configuration, we need
    # to remove orphaned entities
    async_remove_orphaned_entities(
        hass,
        config_entry.entry_id,
        coordinator.mac,
        SWITCH_PLATFORM,
        coordinator.device.status,
        "script",
    )

    # if the climate is removed, from the device configuration, we need
    # to remove orphaned entities
    async_remove_orphaned_entities(
        hass,
        config_entry.entry_id,
        coordinator.mac,
        CLIMATE_PLATFORM,
        coordinator.device.status,
        "thermostat",
    )


class BlockSleepingMotionSwitch(
    ShellySleepingBlockAttributeEntity, RestoreEntity, SwitchEntity
):
    """Entity that controls Motion Sensor on Block based Shelly devices."""

    entity_description: BlockSwitchDescription
    _attr_translation_key = "motion_switch"

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block | None,
        attribute: str,
        description: BlockSwitchDescription,
        entry: RegistryEntry | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        super().__init__(coordinator, block, attribute, description, entry)
        self.last_state: State | None = None

    @property
    def is_on(self) -> bool | None:
        """If motion is active."""
        if self.block is not None:
            return bool(self.block.motionActive)

        if self.last_state is None:
            return None

        return self.last_state.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate switch."""
        await self.coordinator.device.set_shelly_motion_detection(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate switch."""
        await self.coordinator.device.set_shelly_motion_detection(False)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self.last_state = last_state


class BlockRelaySwitch(ShellyBlockAttributeEntity, SwitchEntity):
    """Entity that controls a relay on Block based Shelly devices."""

    entity_description: BlockSwitchDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block,
        attribute: str,
        description: BlockSwitchDescription,
    ) -> None:
        """Initialize relay switch."""
        super().__init__(coordinator, block, attribute, description)
        self.control_result: dict[str, Any] | None = None
        self._attr_unique_id: str = f"{coordinator.mac}-{block.description}"

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        if self.control_result:
            return cast(bool, self.control_result["ison"])

        return bool(self.block.output)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        self.control_result = await self.set_state(turn="on")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        self.control_result = await self.set_state(turn="off")
        self.async_write_ha_state()

    @callback
    def _update_callback(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._update_callback()


class RpcSwitch(ShellyRpcAttributeEntity, SwitchEntity):
    """Entity that controls a switch on RPC based Shelly devices."""

    entity_description: RpcSwitchDescription

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        return self.entity_description.is_on(self.status)

    @rpc_call
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        method = getattr(self.coordinator.device, self.entity_description.method_on)

        if TYPE_CHECKING:
            assert method is not None

        params = self.entity_description.method_params_fn(self._id, True)
        await method(**params)

    @rpc_call
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        method = getattr(self.coordinator.device, self.entity_description.method_off)

        if TYPE_CHECKING:
            assert method is not None

        params = self.entity_description.method_params_fn(self._id, False)
        await method(**params)


class RpcRelaySwitch(RpcSwitch):
    """Entity that controls a switch on RPC based Shelly devices."""

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, key, attribute, description)
        self._attr_unique_id: str = f"{coordinator.mac}-{key}"
