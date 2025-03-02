"""Support for Notion."""

from __future__ import annotations

from dataclasses import dataclass

from aionotion.bridge.models import Bridge
from aionotion.listener.models import Listener, ListenerKind

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import NotionDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class NotionEntityDescription:
    """Define an description for Notion entities."""

    listener_kind: ListenerKind


class NotionEntity(CoordinatorEntity[NotionDataUpdateCoordinator]):
    """Define a base Notion entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NotionDataUpdateCoordinator,
        listener_id: str,
        sensor_id: str,
        bridge_id: int,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        sensor = self.coordinator.data.sensors[sensor_id]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor.hardware_id)},
            manufacturer="Silicon Labs",
            model=str(sensor.hardware_revision),
            name=str(sensor.name).capitalize(),
            sw_version=sensor.firmware_version,
        )

        if bridge := self._async_get_bridge(bridge_id):
            self._attr_device_info["via_device"] = (DOMAIN, bridge.hardware_id)

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = listener_id
        self._bridge_id = bridge_id
        self._listener_id = listener_id
        self._sensor_id = sensor_id
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self._listener_id in self.coordinator.data.listeners
        )

    @property
    def listener(self) -> Listener:
        """Return the listener related to this entity."""
        return self.coordinator.data.listeners[self._listener_id]

    @callback
    def _async_get_bridge(self, bridge_id: int) -> Bridge | None:
        """Get a bridge by ID (if it exists)."""
        if (bridge := self.coordinator.data.bridges.get(bridge_id)) is None:
            LOGGER.debug("Entity references a non-existent bridge ID: %s", bridge_id)
            return None
        return bridge

    @callback
    def _async_update_bridge_id(self) -> None:
        """Update the entity's bridge ID if it has changed.

        Sensors can move to other bridges based on signal strength, etc.
        """
        sensor = self.coordinator.data.sensors[self._sensor_id]

        # If the bridge ID hasn't changed, return:
        if self._bridge_id == sensor.bridge.id:
            return

        # If the bridge doesn't exist, return:
        if (bridge := self._async_get_bridge(sensor.bridge.id)) is None:
            return

        self._bridge_id = sensor.bridge.id

        device_registry = dr.async_get(self.hass)
        this_device = device_registry.async_get_device(
            identifiers={(DOMAIN, sensor.hardware_id)}
        )
        bridge = self.coordinator.data.bridges[self._bridge_id]
        bridge_device = device_registry.async_get_device(
            identifiers={(DOMAIN, bridge.hardware_id)}
        )

        if not bridge_device or not this_device:
            return

        device_registry.async_update_device(
            this_device.id, via_device_id=bridge_device.id
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        if self._listener_id in self.coordinator.data.listeners:
            self._async_update_bridge_id()
        super()._handle_coordinator_update()
