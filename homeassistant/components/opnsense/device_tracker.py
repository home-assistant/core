"""Device tracker support for OPNsense routers."""

from typing import override

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
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
    tracked_devices = entry.runtime_data.tracked_devices

    coordinator = OPNsenseDeviceTrackerCoordinator(hass, entry, client, interfaces)
    entry.runtime_data.tracker_coordinator = coordinator

    def _async_add_new_entities() -> None:
        """Rename the devices of renamed clients and add new clients."""
        if not coordinator.data:
            return

        # Done here because disabled trackers do not listen to the coordinator
        device_registry = dr.async_get(hass)
        for mac_address, device_data in coordinator.data.items():
            if (
                (hostname := device_data.get("hostname"))
                and (
                    device_entry := device_registry.async_get_device_by_connection(
                        (dr.CONNECTION_NETWORK_MAC, mac_address), entry.entry_id
                    )
                )
                and device_entry.name != hostname
            ):
                device_registry.async_update_device(device_entry.id, name=hostname)

        entities = []
        for mac_address in coordinator.data:
            if mac_address in tracked_devices:
                continue
            entity = OPNsenseDeviceTrackerEntity(coordinator, mac_address)
            tracked_devices.add(mac_address)
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
        connection = (dr.CONNECTION_NETWORK_MAC, mac_address)
        self._attr_device_info = dr.DeviceInfo(connections={connection})
        if hostname := self.hostname:
            self._attr_device_info.name = hostname
        elif not dr.async_get(coordinator.hass).async_get_device_by_connection(
            connection, coordinator.config_entry.entry_id
        ):
            # Only name a new device by MAC, an existing device keeps its name
            self._attr_device_info.name = mac_address

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
    def ip_address(self) -> str | None:
        """Return the primary IP address of the device."""
        device_data = self.device_data
        if device_data:
            return device_data.get("ip")
        return None

    @property
    @override
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        device_data = self.device_data
        if device_data:
            hostname = device_data.get("hostname")
            return hostname or None
        return None
