"""Support for the WatchYourLAN service."""

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WatchYourLANUpdateCoordinator

# Define entity descriptions for each sensor type
ONLINE_STATUS_DESCRIPTION = SensorEntityDescription(
    key="online_status",
    name="Online Status",
)

IP_ADDRESS_DESCRIPTION = SensorEntityDescription(
    key="ip_address",
    name="IP Address",
)

MAC_ADDRESS_DESCRIPTION = SensorEntityDescription(
    key="mac_address",
    name="MAC Address",
)

IFACE_DESCRIPTION = SensorEntityDescription(
    key="iface",
    name="Network Interface",
)


# Utility function for setting up device info consistently
def build_device_info(device, domain):
    """Build device info helper function."""
    return {
        "identifiers": {(domain, device.get("ID", "Unknown"))},
        "name": device.get("Name") or f"WatchYourLAN {device.get('ID', 'Unknown')}",
        "manufacturer": device.get("Hw", "Unknown Manufacturer"),
        "model": "WatchYourLAN Device",
        "sw_version": device.get("Last_Seen", "Unknown"),
    }


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the WatchYourLAN sensors."""
    coordinator = entry.runtime_data["coordinator"]

    # Define a list that can store multiple sensor types
    entities: list[SensorEntity | CoordinatorEntity] = []

    # Create device count sensor
    entities.append(WatchYourLANDeviceCountSensor(coordinator))

    # Loop over each device and create sensors for online status, IP, MAC, and Iface
    for device in coordinator.data:
        if isinstance(device, dict):
            entities.append(
                WatchYourLANSensor(coordinator, device)
            )  # Online/Offline sensor
            entities.append(WatchYourLANIPSensor(coordinator, device))  # IP sensor
            entities.append(WatchYourLANMacSensor(coordinator, device))  # MAC sensor
            entities.append(
                WatchYourLANIfaceSensor(coordinator, device)
            )  # Iface sensor

    # Add all the entities
    async_add_entities(entities)


class WatchYourLANSensor(CoordinatorEntity, RestoreSensor, SensorEntity):
    """Representation of a WatchYourLAN online/offline sensor."""

    def __init__(
        self, coordinator: WatchYourLANUpdateCoordinator, device: dict
    ) -> None:
        """Initialize the sensor for online/offline state."""
        super().__init__(coordinator)
        self.device = device
        self.entity_description = ONLINE_STATUS_DESCRIPTION

        # Set the unique ID and device info
        self._attr_unique_id = f"{self.device.get('ID')}_online_status"
        self._attr_device_info = build_device_info(self.device, DOMAIN)

        # Set an appropriate icon for the sensor
        self._attr_icon = (
            "mdi:lan-connect"
            if self.device.get("Now", 0) == 1
            else "mdi:lan-disconnect"
        )

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        return "Online" if self.device.get("Now", 0) == 1 else "Offline"

    async def async_update(self):
        """Update the sensor's state from the coordinator."""
        await (
            self.coordinator.async_request_refresh()
        )  # Request data update from the coordinator
        self._attr_native_value = (
            "Online" if self.device.get("Now", 0) == 1 else "Offline"
        )


class WatchYourLANIPSensor(CoordinatorEntity, RestoreSensor, SensorEntity):
    """Sensor for the IP address of the device."""

    def __init__(
        self, coordinator: WatchYourLANUpdateCoordinator, device: dict
    ) -> None:
        """Initialize the IP address sensor."""
        super().__init__(coordinator)
        self.device = device
        self.entity_description = IP_ADDRESS_DESCRIPTION

        # Set the unique ID and device info
        self._attr_unique_id = f"{self.device.get('ID')}_ip"
        self._attr_device_info = build_device_info(self.device, DOMAIN)

        # Set an appropriate icon for the IP address sensor
        self._attr_icon = "mdi:ip-network"

    @property
    def native_value(self) -> str:
        """Return the native value of the IP address."""
        return self.device.get("IP", "Unknown")

    async def async_update(self):
        """Update the sensor's state from the coordinator."""
        await self.coordinator.async_request_refresh()
        self._attr_native_value = self.device.get("IP", "Unknown")


class WatchYourLANMacSensor(CoordinatorEntity, RestoreSensor, SensorEntity):
    """Sensor for the MAC address of the device."""

    def __init__(
        self, coordinator: WatchYourLANUpdateCoordinator, device: dict
    ) -> None:
        """Initialize the MAC address sensor."""
        super().__init__(coordinator)
        self.device = device
        self.entity_description = MAC_ADDRESS_DESCRIPTION

        # Set the unique ID and device info
        self._attr_unique_id = f"{self.device.get('ID')}_mac"
        self._attr_device_info = build_device_info(self.device, DOMAIN)

        # Set an appropriate icon for the MAC address sensor
        self._attr_icon = "mdi:lan"

    @property
    def native_value(self) -> str:
        """Return the native value of the MAC address."""
        return self.device.get("Mac", "Unknown")

    async def async_update(self):
        """Update the sensor's state from the coordinator."""
        await self.coordinator.async_request_refresh()
        self._attr_native_value = self.device.get("Mac", "Unknown")


class WatchYourLANIfaceSensor(CoordinatorEntity, RestoreSensor, SensorEntity):
    """Sensor for the network interface (Iface) of the device."""

    def __init__(
        self, coordinator: WatchYourLANUpdateCoordinator, device: dict
    ) -> None:
        """Initialize the network interface sensor."""
        super().__init__(coordinator)
        self.device = device
        self.entity_description = IFACE_DESCRIPTION

        # Set the unique ID and device info
        self._attr_unique_id = f"{self.device.get('ID')}_iface"
        self._attr_device_info = build_device_info(self.device, DOMAIN)

        # Set an appropriate icon for the network interface sensor
        self._attr_icon = "mdi:ethernet"

    @property
    def native_value(self) -> str:
        """Return the native value of the network interface."""
        return self.device.get("Iface", "Unknown")

    async def async_update(self):
        """Update the sensor's state from the coordinator."""
        await self.coordinator.async_request_refresh()
        self._attr_native_value = self.device.get("Iface", "Unknown")


class WatchYourLANDeviceCountSensor(CoordinatorEntity, SensorEntity):
    """Sensor that tracks the total number of devices."""

    def __init__(self, coordinator: WatchYourLANUpdateCoordinator) -> None:
        """Initialize the device count sensor."""
        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "WatchYourLAN Total Devices"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return (
            len(self.coordinator.data) if isinstance(self.coordinator.data, list) else 0
        )

    @property
    def extra_state_attributes(self):
        """Return additional details such as known/unknown devices and devices per network interface."""
        if isinstance(self.coordinator.data, list):
            online_count = sum(
                1 for device in self.coordinator.data if device.get("Now") == 1
            )
            offline_count = len(self.coordinator.data) - online_count
            known_count = sum(
                1 for device in self.coordinator.data if device.get("Known") == 1
            )
            unknown_count = len(self.coordinator.data) - known_count

            iface_counts = {}
            for device in self.coordinator.data:
                iface = device.get("Iface", "Unknown")
                iface_counts[iface] = iface_counts.get(iface, 0) + 1

            return {
                "online": online_count,
                "offline": offline_count,
                "total": len(self.coordinator.data),
                "known": known_count,
                "unknown": unknown_count,
                "devices_per_iface": iface_counts,
            }
        return {}
