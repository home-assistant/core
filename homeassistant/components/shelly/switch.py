"""Switch for Shelly."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from aioshelly.block_device import Block

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ShellyBlockCoordinator, ShellyRpcCoordinator, get_entry_data
from .entity import (
    BlockEntityDescription,
    ShellyBlockAttributeEntity,
    ShellyBlockEntity,
    ShellyRpcEntity,
    async_setup_block_attribute_entities,
)
from .utils import (
    async_remove_shelly_entity,
    get_device_entry_gen,
    get_rpc_key_ids,
    is_block_channel_type_light,
    is_rpc_channel_type_light,
)


@dataclass
class BlockSwitchDescription(BlockEntityDescription, SwitchEntityDescription):
    """Class to describe a BLOCK switch."""


GAS_VALVE_SWITCH = BlockSwitchDescription(
    key="valve|valve",
    name="Valve opened",
    icon="mdi:valve",
    available=lambda block: block.valve not in ("failure", "checking"),
    removal_condition=lambda _, block: block.valve in ("not_connected", "unknown"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for device."""
    if get_device_entry_gen(config_entry) == 2:
        return async_setup_rpc_entry(hass, config_entry, async_add_entities)

    return async_setup_block_entry(hass, config_entry, async_add_entities)


@callback
def async_setup_block_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities for block device."""
    coordinator = get_entry_data(hass)[config_entry.entry_id].block
    assert coordinator

    # Add Shelly Gas Valve as a switch
    if coordinator.model == "SHGS-1":
        async_setup_block_attribute_entities(
            hass,
            async_add_entities,
            coordinator,
            {("valve", "valve"): GAS_VALVE_SWITCH},
            BlockValveSwitch,
        )

    # In roller mode the relay blocks exist but do not contain required info
    if (
        coordinator.model in ["SHSW-21", "SHSW-25"]
        and coordinator.device.settings["mode"] != "relay"
    ):
        return

    relay_blocks = []
    assert coordinator.device.blocks
    for block in coordinator.device.blocks:
        if block.type != "relay" or is_block_channel_type_light(
            coordinator.device.settings, int(block.channel)
        ):
            continue

        relay_blocks.append(block)
        unique_id = f"{coordinator.mac}-{block.type}_{block.channel}"
        async_remove_shelly_entity(hass, "light", unique_id)

    if not relay_blocks:
        return

    async_add_entities(BlockRelaySwitch(coordinator, block) for block in relay_blocks)


@callback
def async_setup_rpc_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    coordinator = get_entry_data(hass)[config_entry.entry_id].rpc
    assert coordinator
    switch_key_ids = get_rpc_key_ids(coordinator.device.status, "switch")

    switch_ids = []
    for id_ in switch_key_ids:
        if is_rpc_channel_type_light(coordinator.device.config, id_):
            continue

        switch_ids.append(id_)
        unique_id = f"{coordinator.mac}-switch:{id_}"
        async_remove_shelly_entity(hass, "light", unique_id)

    if not switch_ids:
        return

    async_add_entities(RpcRelaySwitch(coordinator, id_) for id_ in switch_ids)


class BlockValveSwitch(ShellyBlockAttributeEntity, SwitchEntity):
    """Entity that controls a Gas Valve on Block based Shelly devices."""

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block,
        attribute: str,
        description: BlockSwitchDescription,
    ) -> None:
        """Initialize relay switch."""
        super().__init__(coordinator, block, attribute, description)

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        return self.attribute_value in ("closing", "opening", "opened")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        await self.async_set_valve("open")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        await self.async_set_valve("close")

    async def async_set_valve(self, new_state: str) -> None:
        """Set the valve state."""
        await self.coordinator.device.http_request(
            "get", f"settings/{self.block.type}/{self.block.channel}", {"go": new_state}
        )
        self.async_write_ha_state()


class BlockRelaySwitch(ShellyBlockEntity, SwitchEntity):
    """Entity that controls a relay on Block based Shelly devices."""

    def __init__(self, coordinator: ShellyBlockCoordinator, block: Block) -> None:
        """Initialize relay switch."""
        super().__init__(coordinator, block)
        self.control_result: dict[str, Any] | None = None

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


class RpcRelaySwitch(ShellyRpcEntity, SwitchEntity):
    """Entity that controls a relay on RPC based Shelly devices."""

    def __init__(self, coordinator: ShellyRpcCoordinator, id_: int) -> None:
        """Initialize relay switch."""
        super().__init__(coordinator, f"switch:{id_}")
        self._id = id_

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        return bool(self.status["output"])

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        await self.call_rpc("Switch.Set", {"id": self._id, "on": True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        await self.call_rpc("Switch.Set", {"id": self._id, "on": False})
