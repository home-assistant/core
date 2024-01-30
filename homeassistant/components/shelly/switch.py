"""Switch for Shelly."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, cast

from aioshelly.block_device import Block
from aioshelly.const import MODEL_2, MODEL_25, RPC_GENERATIONS

from homeassistant.components.climate import DOMAIN as CLIMATE_PLATFORM
from homeassistant.components.switch import (
    DOMAIN as SWITCH_PLATFORM,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_SLEEP_PERIOD, MOTION_MODELS
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    BlockEntityDescription,
    RpcEntityDescription,
    ShellyBlockEntity,
    ShellyRpcAttributeEntity,
    ShellySleepingBlockAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rpc,
)
from .utils import (
    async_remove_orphaned_entities,
    get_device_entry_gen,
    get_virtual_component_ids,
    is_block_channel_type_light,
    is_rpc_exclude_from_relay,
)


@dataclass(frozen=True, kw_only=True)
class BlockSwitchDescription(BlockEntityDescription, SwitchEntityDescription):
    """Class to describe a BLOCK switch."""


MOTION_SWITCH = BlockSwitchDescription(
    key="sensor|motionActive",
    name="Motion detection",
    entity_category=EntityCategory.CONFIG,
)


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
        return async_setup_entry_rpc(
            hass, config_entry, async_add_entities, RPC_SWITCHES, RpcRelaySwitch
        )

    return async_setup_entry_attribute_entities(
        hass, config_entry, async_add_entities, SWITCHES, BlockRelaySwitch
    )


class BlockRelaySwitch(ShellyBlockAttributeEntity, SwitchEntity):
    """Entity that controls a relay on Block based Shelly devices."""

    entity_description: BlockSwitchDescription
    _attr_translation_key = "valve_switch"

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block,
        attribute: str,
        description: BlockSwitchDescription,
    ) -> None:
        """Initialize relay switch."""
        super().__init__(coordinator, block, attribute, description)
        self._attr_unique_id: str = f"{super().unique_id}"
        self.control_result: dict[str, Any] | None = None
        self._valve = description.name == "Valve"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        if self._valve:
            async_create_issue(
                self.hass,
                DOMAIN,
                "deprecated_valve_switch",
                breaks_in_ha_version="2024.7.0",
                is_fixable=True,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_valve_switch",
                translation_placeholders={
                    "entity": f"{VALVE_DOMAIN}.{cast(str, self.name).lower().replace(' ', '_')}",
                    "service": f"{VALVE_DOMAIN}.open_valve",
                },
            )
            self.control_result = await self.set_state(go="open")
        else:
            self.control_result = await self.set_state(turn="on")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        if self._valve:
            async_create_issue(
                self.hass,
                DOMAIN,
                "deprecated_valve_switch",
                breaks_in_ha_version="2024.7.0",
                is_fixable=True,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_valve_switche",
                translation_placeholders={
                    "entity": f"{VALVE_DOMAIN}.{cast(str, self.name).lower().replace(' ', '_')}",
                    "service": f"{VALVE_DOMAIN}.close_valve",
                },
            )
            self.control_result = await self.set_state(go="close")
        else:
            self.control_result = await self.set_state(turn="off")
        self.async_write_ha_state()

    @callback
    def _update_callback(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._update_callback()

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        await super().async_added_to_hass()

        entity_automations = automations_with_entity(self.hass, self.entity_id)
        entity_scripts = scripts_with_entity(self.hass, self.entity_id)
        for item in entity_automations + entity_scripts:
            async_create_issue(
                self.hass,
                DOMAIN,
                f"deprecated_valve_{self.entity_id}_{item}",
                breaks_in_ha_version="2024.7.0",
                is_fixable=True,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_valve_switch_entity",
                translation_placeholders={
                    "entity": f"{SWITCH_DOMAIN}.{cast(str, self.name).lower().replace(' ', '_')}",
                    "info": item,
                },
            )

    @callback
    def _update_callback(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None

        super()._update_callback()


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
        self._attr_unique_id: str = f"{super().unique_id}"
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


class RpcRelaySwitch(ShellyRpcAttributeEntity, SwitchEntity):
    """Entity that controls a relay on RPC based Shelly devices."""

    entity_description: RpcSwitchDescription

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
