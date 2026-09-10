"""Device tracker support for OPNsense routers."""

from typing import override

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import OPNsenseConfigEntry, OPNsenseCoordinator
from .types import DeviceDetails


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OPNsenseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for OPNsense component."""
    coordinator = entry.runtime_data.coordinator
    tracked_trackers: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add entities for newly discovered devices."""
        if not coordinator.data:
            return

        entities = []
        for mac_address in coordinator.data:
            if mac_address in tracked_trackers:
                continue
            entity = OPNsenseDeviceTrackerEntity(coordinator, mac_address)
            tracked_trackers.add(mac_address)
            entities.append(entity)

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))

    _async_add_new_entities()


class OPNsenseDeviceTrackerEntity(
    CoordinatorEntity[OPNsenseCoordinator], ScannerEntity
):
    """Representation of a tracked device."""

    def __init__(
        self,
        coordinator: OPNsenseCoordinator,
        mac_address: str,
    ) -> None:
        """Initialize the device tracker entity."""
        super().__init__(coordinator)
        self._attr_mac_address = format_mac(mac_address)

    @property
    def device_data(self) -> DeviceDetails | None:
        """Return device data for current device."""
        if self.coordinator.data and self.mac_address in self.coordinator.data:
            return self.coordinator.data[self.mac_address]
        return None

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return (
            self.coordinator.data is not None
            and self.mac_address in self.coordinator.data
        )

    @property
    @override
    def name(self) -> str:
        """Return device name."""
        device_data = self.device_data
        if device_data and device_data.get("hostname"):
            return str(device_data["hostname"])
        return f"OPNsense {self.mac_address}"

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the primary IP address of the device."""
        device_data = self.device_data
        if device_data:
            ip = device_data.get("ip")
            if ip:
                return str(ip)
        return None

    @property
    @override
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        device_data = self.device_data
        if device_data:
            hostname = device_data.get("hostname")
            if hostname:
                return str(hostname)
        return None
