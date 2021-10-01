"""Switch for Shelly."""
from __future__ import annotations

from typing import Any, cast

from aioshelly.block_device import Block

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BlockDeviceWrapper, RpcDeviceWrapper
from .const import BLOCK, DATA_CONFIG_ENTRY, DOMAIN, RPC
from .entity import ShellyBlockEntity, ShellyRpcEntity
from .utils import (
    async_remove_shelly_entity,
    get_device_entry_gen,
    get_rpc_key_ids,
    is_block_channel_type_light,
    is_rpc_channel_type_light,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for device."""
    if get_device_entry_gen(config_entry) == 2:
        return await async_setup_rpc_entry(hass, config_entry, async_add_entities)

    return await async_setup_block_entry(hass, config_entry, async_add_entities)


async def async_setup_block_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities for block device."""
    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][BLOCK]

    # In roller mode the relay blocks exist but do not contain required info
    if (
        wrapper.model in ["SHSW-21", "SHSW-25"]
        and wrapper.device.settings["mode"] != "relay"
    ):
        return

    relay_blocks = []
    assert wrapper.device.blocks
    for block in wrapper.device.blocks:
        if block.type != "relay" or is_block_channel_type_light(
            wrapper.device.settings, int(block.channel)
        ):
            continue

        relay_blocks.append(block)
        unique_id = f"{wrapper.mac}-{block.type}_{block.channel}"
        await async_remove_shelly_entity(hass, "light", unique_id)

    if not relay_blocks:
        return

    async_add_entities(BlockRelaySwitch(wrapper, block) for block in relay_blocks)


async def async_setup_rpc_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][RPC]
    switch_key_ids = get_rpc_key_ids(wrapper.device.status, "switch")

    switch_ids = []
    for id_ in switch_key_ids:
        if is_rpc_channel_type_light(wrapper.device.config, id_):
            continue

        switch_ids.append(id_)
        unique_id = f"{wrapper.mac}-switch:{id_}"
        await async_remove_shelly_entity(hass, "light", unique_id)

    if not switch_ids:
        return

    async_add_entities(RpcRelaySwitch(wrapper, id_) for id_ in switch_ids)


class BlockRelaySwitch(ShellyBlockEntity, SwitchEntity):
    """Entity that controls a relay on Block based Shelly devices."""

    def __init__(self, wrapper: BlockDeviceWrapper, block: Block) -> None:
        """Initialize relay switch."""
        super().__init__(wrapper, block)
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

    def __init__(self, wrapper: RpcDeviceWrapper, id_: int) -> None:
        """Initialize relay switch."""
        super().__init__(wrapper, f"switch:{id_}")
        self._id = id_

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        return bool(self.wrapper.device.status[self.key]["output"])

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        await self.call_rpc("Switch.Set", {"id": self._id, "on": True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        await self.call_rpc("Switch.Set", {"id": self._id, "on": False})
