"""Support for UniFi AP Direct access as device tracker using Coordinator."""

from typing import override

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import UniFiDirectConfigEntry, UniFiDirectDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UniFiDirectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for UniFi AP Direct."""
    coordinator = config_entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_update_devices() -> None:
        """Add new devices from the coordinator."""
        new_entities: list[UniFiScannerEntity] = []
        for mac in coordinator.data:
            if mac not in tracked:
                tracked.add(mac)
                new_entities.append(UniFiScannerEntity(coordinator, mac))
        if new_entities:
            async_add_entities(new_entities)

    config_entry.async_on_unload(coordinator.async_add_listener(_async_update_devices))
    _async_update_devices()


class UniFiScannerEntity(
    CoordinatorEntity[UniFiDirectDataUpdateCoordinator], ScannerEntity
):
    """Representation of a device connected to a UniFi AP Direct."""

    def __init__(self, coordinator: UniFiDirectDataUpdateCoordinator, mac: str) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self._mac = mac
        device = coordinator.data.get(mac, {})
        self._attr_device_info = dr.DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            name=device.get("hostname") or mac,
        )

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected to the AP."""
        return self._mac in self.coordinator.data

    @property
    @override
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the IP address of the device."""
        if device := self.coordinator.data.get(self._mac):
            return device.get("ip")
        return None

    @property
    @override
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        if device := self.coordinator.data.get(self._mac):
            return device.get("hostname")
        return None
