"""Support for Mikrotik routers as device tracker."""

from typing import Any, override

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    ScannerEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MikrotikConfigEntry, MikrotikDataUpdateCoordinator
from .device import Device
from .entity import MikrotikBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MikrotikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for Mikrotik component."""
    coordinator = config_entry.runtime_data

    registry = er.async_get(hass)

    # Restore clients that is not a part of active clients list.
    for entity in registry.entities.get_entries_for_config_entry_id(
        config_entry.entry_id
    ):
        if entity.domain == DEVICE_TRACKER_DOMAIN:
            if (
                entity.unique_id in coordinator.api.devices
                or entity.unique_id not in coordinator.api.all_devices
            ):
                continue
            coordinator.api.restore_device(entity.unique_id)

    @callback
    def update_hub() -> None:
        """Update the status of the device."""
        update_items(coordinator, async_add_entities)

    config_entry.async_on_unload(coordinator.async_add_listener(update_hub))

    update_hub()


@callback
def update_items(
    coordinator: MikrotikDataUpdateCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Update tracked device state from the hub."""
    new_tracked: list[MikrotikDataUpdateCoordinatorTracker] = []
    # A poll in the executor can add clients meanwhile
    for mac, device in list(coordinator.api.devices.items()):
        if mac not in coordinator.tracked_macs:
            coordinator.tracked_macs.add(mac)
            new_tracked.append(
                MikrotikDataUpdateCoordinatorTracker(
                    device, coordinator, _client_device_info(coordinator, device)
                )
            )

    async_add_entities(new_tracked)


@callback
def _client_device_info(
    coordinator: MikrotikDataUpdateCoordinator, device: Device
) -> DeviceInfo:
    """Return device info which never renames a device to its MAC."""
    connection = (CONNECTION_NETWORK_MAC, device.mac)
    if (name := device.host_name) is None and dr.async_get(
        coordinator.hass
    ).async_get_device_by_connection(connection, coordinator.config_entry.entry_id):
        return DeviceInfo(connections={connection})
    return DeviceInfo(connections={connection}, name=name or device.mac)


class MikrotikDataUpdateCoordinatorTracker(MikrotikBaseEntity, ScannerEntity):
    """Representation of network device."""

    def __init__(
        self,
        device: Device,
        coordinator: MikrotikDataUpdateCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator, EntityDescription(key=device.mac))
        self.device = device
        self._attr_unique_id = device.mac
        self._attr_device_info = device_info

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the client is connected to the network."""
        return self.coordinator.is_client_connected(self.device)

    @property
    @override
    def hostname(self) -> str:
        """Return the hostname of the client."""
        return self.device.name

    @property
    @override
    def mac_address(self) -> str:
        """Return the mac address of the client."""
        return self.device.mac

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the mac address of the client."""
        return self.device.ip_address

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device state attributes."""
        return self.device.attrs if self.is_connected else None
