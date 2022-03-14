"""Switch for Shelly."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from aioshelly.block_device import Block

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry

from . import BlockDeviceWrapper
from .const import CONF_SLEEP_PERIOD, LOGGER
from .entity import (
    BlockEntityDescription,
    RpcEntityDescription,
    ShellyBlockAttributeEntity,
    ShellyRpcAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rpc,
)
from .utils import (
    get_device_entry_gen,
    is_block_exclude_from_relay,
    is_rpc_channel_type_light,
)


@dataclass
class BlockSwitchDescription(BlockEntityDescription, SwitchEntityDescription):
    """Class to describe a BLOCK sensor."""


@dataclass
class RpcSwitchDescription(RpcEntityDescription, SwitchEntityDescription):
    """Class to describe a RPC sensor."""


SWITCHES: Final = {
    ("relay", "output"): BlockSwitchDescription(
        key="relay|output",
        name="",
        removal_condition=is_block_exclude_from_relay,
    ),
}

RPC_SWITCHES: Final = {
    "switch": RpcSwitchDescription(
        key="switch",
        sub_key="output",
        name="Switch",
        removal_condition=is_rpc_channel_type_light,
    )
}


def _build_block_description(entry: RegistryEntry) -> BlockSwitchDescription:
    """Build description when restoring block attribute entities."""
    return BlockSwitchDescription(
        key="",
        name="",
        icon=entry.original_icon,
    )


async def _async_migrate_unique_ids(
    hass: HomeAssistant, config_entry: ConfigEntry, switches: dict
) -> None:
    """Migrate old entry."""

    gen = config_entry.data["gen"]
    suffix = "output" if gen == 1 else "switch"

    @callback
    def _async_migrator(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:

        # Only switches entities need to be updated
        if entity_entry.domain != "switch":
            return None

        # Old format for switch entities was {device_unique_id}_{block.type}_{block.channel}.....
        # New format is {device_unique_id}_{block.type}_{block.channel}_{block.key}.....

        old_unique_id = entity_entry.unique_id

        for switch in switches:
            sensor_type = switch[1] if gen == 1 else switch
            if old_unique_id.endswith(sensor_type):
                return None

        new_unique_id = f"{old_unique_id}-{suffix}"

        LOGGER.debug(
            "Migrating switch unique_id from [%s] to [%s]",
            old_unique_id,
            new_unique_id,
        )
        return {"new_unique_id": new_unique_id}

    await er.async_migrate_entries(hass, config_entry.entry_id, _async_migrator)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for device."""
    if get_device_entry_gen(config_entry) == 2:

        await _async_migrate_unique_ids(hass, config_entry, RPC_SWITCHES)

        return await async_setup_entry_rpc(
            hass, config_entry, async_add_entities, RPC_SWITCHES, RpcRelaySwitch
        )

    await _async_migrate_unique_ids(hass, config_entry, SWITCHES)

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
