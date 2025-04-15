"""Switch for Shelly."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

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

from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    BlockEntityDescription,
    RpcEntityDescription,
    ShellyBlockAttributeEntity,
    ShellyRpcAttributeEntity,
    ShellySleepingBlockAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rpc,
)
from .utils import (
    async_remove_orphaned_entities,
    get_device_entry_gen,
    get_virtual_component_ids,
    is_block_exclude_from_relay,
    is_rpc_exclude_from_relay,
)


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
        method_on="Switch.Set",
        method_off="Switch.Set",
        method_params_fn=lambda id, value: {"id": id, "on": value},
    ),
}

RPC_SWITCHES = {
    "boolean": RpcSwitchDescription(
        key="boolean",
        sub_key="value",
        is_on=lambda status: bool(status["value"]),
        method_on="Boolean.Set",
        method_off="Boolean.Set",
        method_params_fn=lambda id, value: {"id": id, "value": value},
    ),
    "script": RpcSwitchDescription(
        key="script",
        sub_key="running",
        is_on=lambda status: bool(status["running"]),
        method_on="Script.Start",
        method_off="Script.Stop",
        method_params_fn=lambda id, _: {"id": id},
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
    _attr_has_entity_name = True

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        return self.entity_description.is_on(self.status)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        await self.call_rpc(
            self.entity_description.method_on,
            self.entity_description.method_params_fn(self._id, True),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        await self.call_rpc(
            self.entity_description.method_off,
            self.entity_description.method_params_fn(self._id, False),
        )


class RpcRelaySwitch(RpcSwitch):
    """Entity that controls a switch on RPC based Shelly devices."""

    # False to avoid double naming as True is inerithed from base class
    _attr_has_entity_name = False

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
