"""Valve for Shelly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from aioshelly.block_device import Block
from aioshelly.const import BLOCK_GENERATIONS, MODEL_GAS

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODEL_FRANKEVER_WATER_VALVE, MODEL_NEO_WATER_VALVE
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    BlockEntityDescription,
    RpcEntityDescription,
    ShellyBlockAttributeEntity,
    ShellyRpcAttributeEntity,
    async_setup_block_attribute_entities,
    async_setup_entry_rpc,
)
from .utils import async_remove_shelly_entity, get_device_entry_gen

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class BlockValveDescription(BlockEntityDescription, ValveEntityDescription):
    """Class to describe a BLOCK valve."""


@dataclass(kw_only=True, frozen=True)
class RpcValveDescription(RpcEntityDescription, ValveEntityDescription):
    """Class to describe a RPC virtual valve."""


GAS_VALVE = BlockValveDescription(
    key="valve|valve",
    name="Valve",
    available=lambda block: block.valve not in ("failure", "checking"),
    removal_condition=lambda _, block: block.valve in ("not_connected", "unknown"),
)


class RpcShellyBaseWaterValve(ShellyRpcAttributeEntity, ValveEntity):
    """Base Entity for RPC Shelly Water Valves."""

    entity_description: RpcValveDescription
    _attr_device_class = ValveDeviceClass.WATER
    _id: int

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcEntityDescription,
    ) -> None:
        """Initialize RPC water valve."""
        super().__init__(coordinator, key, attribute, description)
        self._attr_name = None  # Main device entity


class RpcShellyWaterValve(RpcShellyBaseWaterValve):
    """Entity that controls a valve on RPC Shelly Water Valve."""

    _attr_supported_features = (
        ValveEntityFeature.OPEN
        | ValveEntityFeature.CLOSE
        | ValveEntityFeature.SET_POSITION
    )
    _attr_reports_position = True

    @property
    def current_valve_position(self) -> int:
        """Return current position of valve."""
        return cast(int, self.attribute_value)

    async def async_set_valve_position(self, position: int) -> None:
        """Move the valve to a specific position."""
        await self.coordinator.device.number_set(self._id, position)


class RpcShellyNeoWaterValve(RpcShellyBaseWaterValve):
    """Entity that controls a valve on RPC Shelly NEO Water Valve."""

    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_reports_position = False

    @property
    def is_closed(self) -> bool | None:
        """Return if the valve is closed or not."""
        return not self.attribute_value

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open valve."""
        await self.call_rpc("Boolean.Set", {"id": self._id, "value": True})

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close valve."""
        await self.call_rpc("Boolean.Set", {"id": self._id, "value": False})


RPC_VALVES: dict[str, RpcValveDescription] = {
    "water_valve": RpcValveDescription(
        key="number",
        sub_key="value",
        role="position",
        entity_class=RpcShellyWaterValve,
        models={MODEL_FRANKEVER_WATER_VALVE},
    ),
    "neo_water_valve": RpcValveDescription(
        key="boolean",
        sub_key="value",
        role="state",
        entity_class=RpcShellyNeoWaterValve,
        models={MODEL_NEO_WATER_VALVE},
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up valves for device."""
    if get_device_entry_gen(config_entry) in BLOCK_GENERATIONS:
        return async_setup_block_entry(hass, config_entry, async_add_entities)

    return async_setup_rpc_entry(hass, config_entry, async_add_entities)


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
        hass, config_entry, async_add_entities, RPC_VALVES, RpcShellyWaterValve
    )


@callback
def async_setup_block_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up valve for device."""
    coordinator = config_entry.runtime_data.block
    assert coordinator and coordinator.device.blocks

    if coordinator.model == MODEL_GAS:
        async_setup_block_attribute_entities(
            hass,
            async_add_entities,
            coordinator,
            {("valve", "valve"): GAS_VALVE},
            BlockShellyValve,
        )
        # Remove deprecated switch entity for gas valve
        unique_id = f"{coordinator.mac}-valve_0-valve"
        async_remove_shelly_entity(hass, "switch", unique_id)


class BlockShellyValve(ShellyBlockAttributeEntity, ValveEntity):
    """Entity that controls a valve on block based Shelly devices."""

    entity_description: BlockValveDescription
    _attr_device_class = ValveDeviceClass.GAS
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block,
        attribute: str,
        description: BlockValveDescription,
    ) -> None:
        """Initialize block valve."""
        super().__init__(coordinator, block, attribute, description)
        self.control_result: dict[str, Any] | None = None
        self._attr_is_closed = bool(self.attribute_value == "closed")

    @property
    def is_closing(self) -> bool:
        """Return if the valve is closing."""
        if self.control_result:
            return cast(bool, self.control_result["state"] == "closing")

        return self.attribute_value == "closing"

    @property
    def is_opening(self) -> bool:
        """Return if the valve is opening."""
        if self.control_result:
            return cast(bool, self.control_result["state"] == "opening")

        return self.attribute_value == "opening"

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open valve."""
        self.control_result = await self.set_state(go="open")
        self.async_write_ha_state()

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close valve."""
        self.control_result = await self.set_state(go="close")
        self.async_write_ha_state()

    @callback
    def _update_callback(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        self._attr_is_closed = bool(self.attribute_value == "closed")
        super()._update_callback()
