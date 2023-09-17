"""Event for Shelly."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import RPC_INPUTS_EVENTS_TYPES
from .coordinator import ShellyRpcCoordinator, get_entry_data
from .utils import (
    async_remove_shelly_entity,
    get_device_entry_gen,
    get_rpc_input_name,
    get_rpc_key_instances,
    is_rpc_momentary_input,
)


@dataclass
class ShellyEventDescription(EventEntityDescription):
    """Class to describe Shelly event."""

    removal_condition: Callable[[dict, dict, str], bool] | None = None


RPC_EVENT: Final = ShellyEventDescription(
    key="input",
    device_class=EventDeviceClass.BUTTON,
    event_types=list(RPC_INPUTS_EVENTS_TYPES),
    removal_condition=lambda config, status, key: not is_rpc_momentary_input(
        config, status, key
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    if get_device_entry_gen(config_entry) == 2:
        coordinator = get_entry_data(hass)[config_entry.entry_id].rpc
        assert coordinator

        entities = []
        key_instances = get_rpc_key_instances(coordinator.device.status, RPC_EVENT.key)

        for key in key_instances:
            if RPC_EVENT.removal_condition and RPC_EVENT.removal_condition(
                coordinator.device.config, coordinator.device.status, key
            ):
                unique_id = f"{coordinator.mac}-{key}"
                async_remove_shelly_entity(hass, EVENT_DOMAIN, unique_id)
            else:
                entities.append(ShellyRpcEvent(coordinator, key, RPC_EVENT))

        async_add_entities(entities)


class ShellyRpcEvent(CoordinatorEntity[ShellyRpcCoordinator], EventEntity):
    """Represent RPC event entity."""

    _attr_should_poll = False
    entity_description: ShellyEventDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        description: ShellyEventDescription,
    ) -> None:
        """Initialize Shelly entity."""
        super().__init__(coordinator)
        self.input_index = int(key.split(":")[-1])
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, coordinator.mac)}
        )
        self._attr_unique_id = f"{coordinator.mac}-{key}"
        self._attr_name = get_rpc_input_name(coordinator.device, key)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_subscribe_input_events(self._async_handle_event)
        )

    @callback
    def _async_handle_event(self, event: dict[str, Any]) -> None:
        """Handle the demo button event."""
        if event["id"] == self.input_index:
            self._trigger_event(event["event"])
            self.async_write_ha_state()
