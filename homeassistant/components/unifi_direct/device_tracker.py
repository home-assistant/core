"""Support for UniFi AP direct access as device tracker using Coordinator."""

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import UniFiDirectDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for UniFi AP direct."""
    coordinator: UniFiDirectDataUpdateCoordinator = config_entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_update_devices() -> None:
        """Add new devices from the coordinator."""
        new_entities: list[UnifiScannerEntity] = []
        for mac in coordinator.data:
            if mac not in tracked:
                tracked.add(mac)
                new_entities.append(UnifiScannerEntity(coordinator, mac))
        if new_entities:
            async_add_entities(new_entities)

    config_entry.async_on_unload(coordinator.async_add_listener(_async_update_devices))
    _async_update_devices()


class UnifiScannerEntity(
    CoordinatorEntity[UniFiDirectDataUpdateCoordinator], ScannerEntity
):
    """Representation of a device connected to a UniFi AP."""

    def __init__(self, coordinator: UniFiDirectDataUpdateCoordinator, mac: str) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self._mac = mac
        device = coordinator.data.get(mac, {})
        self._attr_name = device.get("hostname") or mac

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the AP."""
        return self._mac in self.coordinator.data

    @property
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    @property
    def ip_address(self) -> str | None:
        """Return the IP address of the device."""
        if device := self.coordinator.data.get(self._mac):
            return device.get("ip")
        return None

    @property
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        if device := self.coordinator.data.get(self._mac):
            return device.get("hostname")
        return None
