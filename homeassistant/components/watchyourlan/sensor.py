"""Support for the WatchYourLAN service."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WatchYourLANUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the WatchYourLAN sensors."""
    coordinator = WatchYourLANUpdateCoordinator(hass, entry.data)
    await coordinator.async_config_entry_first_refresh()

    entities = [WatchYourLANDeviceCountSensor(coordinator)]

    if isinstance(coordinator.data, list):
        entities += [
            WatchYourLANSensor(coordinator, device, entry.data)
            for device in coordinator.data
            if isinstance(device, dict)
        ]

    async_add_entities(entities)


class WatchYourLANSensor(SensorEntity):
    """Representation of a WatchYourLAN sensor."""

    def __init__(
        self, coordinator: WatchYourLANUpdateCoordinator, device: dict, config: dict
    ) -> None:
        """Initialize the sensor for a single device."""
        super().__init__()
        self.coordinator = coordinator
        self.device = device
        self.base_url = config["url"]

    @property
    def name(self):
        """Return the name of the sensor, using the format 'WatchYourLAN <ID> <Optionally include name>'."""
        device_id = self.device.get("ID")
        device_name = self.device.get("Name", "").strip()

        if not device_name:
            return f"WatchYourLAN {device_id}"
        return f"WatchYourLAN {device_id} {device_name}"

    @property
    def unique_id(self):
        """Return a unique ID for this sensor based solely on the device's ID."""
        return f"watchyourlan_{self.device.get('ID')}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return "Online" if self.device.get("Now") == 1 else "Offline"

    @property
    def extra_state_attributes(self):
        """Return other attributes related to the device, including the link to the device's page."""
        host_id = self.device.get("ID")
        host_page_url = f"{self.base_url}/host/{host_id}"

        return {
            "ID": self.device.get("ID"),
            "Name": self.device.get("Name"),
            "IP": self.device.get("IP"),
            "Mac": self.device.get("Mac"),
            "Hardware": self.device.get("Hw"),
            "Iface": self.device.get("Iface"),
            "DNS": self.device.get("DNS"),
            "Last_Seen": self.device.get("Date"),
            "Known": self.device.get("Known"),
            "Now": self.device.get("Now"),
            "Host Page": host_page_url,
        }

    @property
    def available(self):
        """Return if the sensor is available."""
        return self.coordinator.last_update_success


class WatchYourLANDeviceCountSensor(SensorEntity):
    """Sensor that tracks the total number of devices."""

    def __init__(self, coordinator: WatchYourLANUpdateCoordinator) -> None:
        """Initialize the device count sensor."""
        super().__init__()
        self.coordinator = coordinator

    @property
    def name(self):
        """Return the name of the sensor."""
        return "WatchYourLAN Total Devices"

    @property
    def state(self):
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
