"""Support for Mikrotik routers as device tracker."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER, SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .hub import Device, MikrotikDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for Mikrotik component."""
    coordinator: MikrotikDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    tracked: dict[str, MikrotikDataUpdateCoordinatorTracker] = {}

    registry = entity_registry.async_get(hass)

    # Restore clients that is not a part of active clients list.
    for entity in registry.entities.values():

        if (
            entity.config_entry_id == config_entry.entry_id
            and entity.domain == DEVICE_TRACKER
        ):

            if (
                entity.unique_id in coordinator.api.devices
                or entity.unique_id not in coordinator.api.all_devices
            ):
                continue
            coordinator.api.restore_device(entity.unique_id)

    @callback
    def update_hub() -> None:
        """Update the status of the device."""
        update_items(coordinator, async_add_entities, tracked)

    config_entry.async_on_unload(coordinator.async_add_listener(update_hub))

    update_hub()


@callback
def update_items(
    coordinator: MikrotikDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
    tracked: dict[str, MikrotikDataUpdateCoordinatorTracker],
) -> None:
    """Update tracked device state from the hub."""
    new_tracked: list[MikrotikDataUpdateCoordinatorTracker] = []
    for mac, device in coordinator.api.devices.items():
        if mac not in tracked:
            tracked[mac] = MikrotikDataUpdateCoordinatorTracker(device, coordinator)
            new_tracked.append(tracked[mac])

    if new_tracked:
        async_add_entities(new_tracked)


class MikrotikDataUpdateCoordinatorTracker(
    CoordinatorEntity[MikrotikDataUpdateCoordinator], ScannerEntity
):
    """Representation of network device."""

    def __init__(
        self, device: Device, coordinator: MikrotikDataUpdateCoordinator
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
    def source_type(self) -> SourceType:
        """Return the source type of the client."""
        return SourceType.ROUTER

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
