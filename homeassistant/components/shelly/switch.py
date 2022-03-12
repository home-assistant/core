"""Switch for Shelly."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from aioshelly.block_device import Block

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry

from . import BlockDeviceWrapper
from .const import CONF_SLEEP_PERIOD
from .entity import (
    BlockEntityDescription,
    RpcEntityDescription,
    ShellyBlockAttributeEntity,
    ShellyRpcAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rpc,
)
from .utils import get_device_entry_gen


@dataclass
class BlockSwitchDescription(BlockEntityDescription, SwitchEntityDescription):
    """Class to describe a BLOCK sensor."""


@dataclass
class RpcSwitchDescription(RpcEntityDescription, SwitchEntityDescription):
    """Class to describe a RPC sensor."""


SWITCHES: Final = {
    ("relay", "input"): BlockSwitchDescription(
        key="relay|input",
        name="Switch",
    ),
}

RPC_SWITCHES: Final = {
    "switch": RpcSwitchDescription(
        key="switch",
        sub_key="output",
        name="Switch",
    ),
}


def _build_block_description(entry: RegistryEntry) -> BlockSwitchDescription:
    """Build description when restoring block attribute entities."""
    return BlockSwitchDescription(
        key="",
        name="",
        icon=entry.original_icon,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for device."""
    if get_device_entry_gen(config_entry) == 2:
        return await async_setup_entry_rpc(
            hass, config_entry, async_add_entities, RPC_SWITCHES, RpcRelaySwitch
        )

    if config_entry.data[CONF_SLEEP_PERIOD]:
        # await async_setup_entry_attribute_entities(
        #     hass,
        #     config_entry,
        #     async_add_entities,
        #     SWITCHES,
        #     BlockSleepingRelaySwitch,
        #     _build_block_description,
        # )
        pass
    else:
        await async_setup_entry_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            SWITCHES,
            BlockRelaySwitch,
            _build_block_description,
        )


class BlockRelaySwitch(ShellyBlockAttributeEntity, SwitchEntity):
    """Entity that controls a relay on Block based Shelly devices."""

    entity_description: BlockSwitchDescription

    def __init__(
        self,
        wrapper: BlockDeviceWrapper,
        block: Block,
        attribute: str,
        description: BlockSwitchDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(wrapper, block, attribute, description)

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        return bool(self.block.output)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        await self.set_state(turn="on")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        await self.set_state(turn="off")
        self.async_write_ha_state()


class RpcRelaySwitch(ShellyRpcAttributeEntity, SwitchEntity):
    """Entity that controls a relay on RPC based Shelly devices."""

    entity_description: RpcSwitchDescription

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        return bool(self.wrapper.device.status[self.key]["output"])

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        await self.call_rpc(
            "Switch.Set",
            {"id": self.status["id"], "on": True},
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        await self.call_rpc(
            "Switch.Set",
            {"id": self.status["id"], "on": False},
        )
