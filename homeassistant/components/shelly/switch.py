"""Switch for Shelly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from aioshelly.block_device import Block
from aioshelly.const import (
    MODEL_2,
    MODEL_25,
    MODEL_GAS,
    MODEL_WALL_DISPLAY,
    RPC_GENERATIONS,
)

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN, GAS_VALVE_OPEN_STATES
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
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
    is_rpc_thermostat_internal_actuator,
    is_rpc_thermostat_mode,
)


@dataclass(frozen=True, kw_only=True)
class BlockSwitchDescription(BlockEntityDescription, SwitchEntityDescription):
    """Class to describe a BLOCK switch."""


# This entity description is deprecated and will be removed in Home Assistant 2024.7.0.
GAS_VALVE_SWITCH = BlockSwitchDescription(
    key="valve|valve",
    name="Valve",
    available=lambda block: block.valve not in ("failure", "checking"),
    removal_condition=lambda _, block: block.valve in ("not_connected", "unknown"),
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for device."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        return async_setup_rpc_entry(hass, config_entry, async_add_entities)

    return async_setup_block_entry(hass, config_entry, async_add_entities)


@callback
def async_setup_block_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities for block device."""
    coordinator = config_entry.runtime_data.block
    assert coordinator

    # Add Shelly Gas Valve as a switch
    if coordinator.model == MODEL_GAS:
        async_setup_block_attribute_entities(
            hass,
            async_add_entities,
            coordinator,
            {("valve", "valve"): GAS_VALVE_SWITCH},
            BlockValveSwitch,
        )
        return

    # In roller mode the relay blocks exist but do not contain required info
    if (
        coordinator.model in [MODEL_2, MODEL_25]
        and coordinator.device.settings["mode"] != "relay"
    ):
        return

    relay_blocks = []
    assert coordinator.device.blocks
    for block in coordinator.device.blocks:
        if (
            block.type != "relay"
            or block.channel is not None
            and is_block_channel_type_light(
                coordinator.device.settings, int(block.channel)
            )
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
    config_entry: ShellyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    coordinator = config_entry.runtime_data.rpc
    assert coordinator
    switch_key_ids = get_rpc_key_ids(coordinator.device.status, "switch")

    switch_ids = []
    for id_ in switch_key_ids:
        if is_rpc_channel_type_light(coordinator.device.config, id_):
            continue

        if coordinator.model == MODEL_WALL_DISPLAY:
            # There are three configuration scenarios for WallDisplay:
            # - relay mode (no thermostat)
            # - thermostat mode using the internal relay as an actuator
            # - thermostat mode using an external (from another device) relay as
            #   an actuator
            if not is_rpc_thermostat_mode(id_, coordinator.device.status):
                # The device is not in thermostat mode, we need to remove a climate
                # entity
                unique_id = f"{coordinator.mac}-thermostat:{id_}"
                async_remove_shelly_entity(hass, "climate", unique_id)
            elif is_rpc_thermostat_internal_actuator(coordinator.device.status):
                # The internal relay is an actuator, skip this ID so as not to create
                # a switch entity
                continue

        switch_ids.append(id_)
        unique_id = f"{coordinator.mac}-switch:{id_}"
        async_remove_shelly_entity(hass, "light", unique_id)

    if not switch_ids:
        return

    async_add_entities(RpcRelaySwitch(coordinator, id_) for id_ in switch_ids)


class BlockValveSwitch(ShellyBlockAttributeEntity, SwitchEntity):
    """Entity that controls a Gas Valve on Block based Shelly devices.

    This class is deprecated and will be removed in Home Assistant 2024.7.0.
    """

    entity_description: BlockSwitchDescription
    _attr_translation_key = "valve_switch"

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block,
        attribute: str,
        description: BlockSwitchDescription,
    ) -> None:
        """Initialize valve."""
        super().__init__(coordinator, block, attribute, description)
        self.control_result: dict[str, Any] | None = None

    @property
    def is_on(self) -> bool:
        """If valve is open."""
        if self.control_result:
            return self.control_result["state"] in GAS_VALVE_OPEN_STATES

        return self.attribute_value in GAS_VALVE_OPEN_STATES

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Open valve."""
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
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Close valve."""
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
        self.async_write_ha_state()

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
