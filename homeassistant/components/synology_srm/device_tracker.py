"""Support for Synology SRM routers as device tracker."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER,
    ScannerEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import (
    Device,
    SynologySRMConfigEntry,
    SynologySRMDataUpdateCoordinator,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SynologySRMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for Synology SRM component."""
    coordinator = config_entry.runtime_data

    tracked: dict[str, SynologySRMDataUpdateCoordinatorTracker] = {}

    registry = er.async_get(hass)

    # Restore clients that is not a part of active clients list.
    for entity in registry.entities.get_entries_for_config_entry_id(
        config_entry.entry_id
    ):
        if entity.domain == DEVICE_TRACKER:
            if (
                entity.unique_id in coordinator.api_client.devices
                or entity.unique_id not in coordinator.api_client.all_devices
            ):
                continue
            coordinator.api_client.restore_device(entity.unique_id)

    @callback
    def update_hub() -> None:
        """Update the status of the device."""
        update_items(coordinator, async_add_entities, tracked)

    config_entry.async_on_unload(coordinator.async_add_listener(update_hub))

    update_hub()


@callback
def update_items(
    coordinator: SynologySRMDataUpdateCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: dict[str, SynologySRMDataUpdateCoordinatorTracker],
) -> None:
    """Update tracked device state from the hub."""
    new_tracked: list[SynologySRMDataUpdateCoordinatorTracker] = []
    for mac, device in coordinator.api_client.devices.items():
        if mac not in tracked:
            tracked[mac] = SynologySRMDataUpdateCoordinatorTracker(device, coordinator)
            new_tracked.append(tracked[mac])

    async_add_entities(new_tracked)


class SynologySRMDataUpdateCoordinatorTracker(
    CoordinatorEntity[SynologySRMDataUpdateCoordinator], ScannerEntity
):
    """Representation of network device."""

    def __init__(
        self, device: Device, coordinator: SynologySRMDataUpdateCoordinator
    ) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self.device = device
        self._attr_name = device.name
        self._attr_unique_id = device.mac

    @property
    def is_connected(self) -> bool:
        """Return true if the client is connected to the network."""
        if (
            self.device.last_seen
            and (dt_util.utcnow() - self.device.last_seen)
            < self.coordinator.option_detection_time
        ):
            return True
        return False

    @property
    def hostname(self) -> str:
        """Return the hostname of the client."""
        return self.device.name

    @property
    def mac_address(self) -> str:
        """Return the mac address of the client."""
        return self.device.mac

    @property
    def ip_address(self) -> str | None:
        """Return the mac address of the client."""
        return self.device.ip_address

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device state attributes."""
        return self.device.attrs if self.is_connected else None
