"""Device tracker support for OPNsense routers."""

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import OPNsenseDeviceTrackerCoordinator
from .types import DeviceDetails, OPNsenseConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OPNsenseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for OPNsense component."""
    client = entry.runtime_data.client
    interfaces = entry.runtime_data.tracker_interfaces

    coordinator = OPNsenseDeviceTrackerCoordinator(hass, entry, client, interfaces)

    def _async_add_new_entities() -> None:
        """Add entities for newly discovered devices."""
        if not coordinator.data:
            return

        entities = []
        for mac_address in coordinator.data:
            if mac_address in coordinator.tracked_devices:
                continue
            entity = OPNsenseDeviceTrackerEntity(coordinator, mac_address)
            coordinator.tracked_devices.add(mac_address)
            entities.append(entity)

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()
    _async_add_new_entities()


class OPNsenseDeviceTrackerEntity(
    CoordinatorEntity[OPNsenseDeviceTrackerCoordinator], ScannerEntity
):
    """Representation of a tracked device."""

    def __init__(
        self,
        coordinator: OPNsenseDeviceTrackerCoordinator,
        mac_address: str,
    ) -> None:
        """Initialize the device tracker entity."""
        super().__init__(coordinator)
        self._attr_mac_address = mac_address

    @property
    def device_data(self) -> DeviceDetails | None:
        """Return device data for current device."""
        if self.coordinator.data and self.mac_address in self.coordinator.data:
            return self.coordinator.data[self.mac_address]
        return None

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return (
            self.coordinator.data is not None
            and self.mac_address in self.coordinator.data
        )

    @property
    def name(self) -> str:
        """Return device name."""
        device_data = self.device_data
        if device_data and device_data.get("hostname"):
            return str(device_data["hostname"])
        return f"OPNsense {self.mac_address}"

    @property
    def ip_address(self) -> str | None:
        """Return the primary IP address of the device."""
        device_data = self.device_data
        if device_data:
            return device_data.get("ip")
        return None

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        device_data = self.device_data
        if device_data:
            hostname = device_data.get("hostname")
            return hostname or None
        return None
