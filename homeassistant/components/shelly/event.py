"""Event for Shelly."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import RPC_INPUTS_EVENTS_TYPES
from .coordinator import ShellyRpcCoordinator, get_entry_data
from .entity import RpcEntityDescription
from .utils import get_device_entry_gen, get_rpc_entity_name, get_rpc_key_instances


@dataclass
class RpcEventDescription(RpcEntityDescription, EventEntityDescription):
    """Class to describe a RPC event."""


RPC_EVENT: Final = RpcEventDescription(
    key="input",
    sub_key="state",
    name="Input",
    device_class=EventDeviceClass.BUTTON,
    event_types=list(RPC_INPUTS_EVENTS_TYPES),
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
            entities.append(ShellyRpcEvent(coordinator, key, RPC_EVENT))

        async_add_entities(entities)


class ShellyRpcEvent(CoordinatorEntity[ShellyRpcCoordinator], EventEntity):
    """Represent a RPC binary sensor entity."""

    _attr_should_poll = False
    entity_description: RpcEventDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        description: RpcEventDescription,
    ) -> None:
        """Initialize Shelly entity."""
        super().__init__(coordinator)
        self.key = key
        self._attr_device_info = {
            "connections": {(CONNECTION_NETWORK_MAC, coordinator.mac)}
        }
        self._attr_unique_id = f"{coordinator.mac}-{key}"
        self._attr_name = get_rpc_entity_name(coordinator.device, key)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.coordinator.async_subscribe_input_events(self._async_handle_event)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        self.coordinator.async_unsubscribe_input_events(self._async_handle_event)

    @callback
    def _async_handle_event(self, event: dict[str, Any]) -> None:
        """Handle the demo button event."""
        if event["component"] == self.key:
            self._trigger_event(event["event"])
            self.async_write_ha_state()
