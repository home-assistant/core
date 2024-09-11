"""Support for the WatchYourLAN service."""

from collections.abc import Sequence
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import WatchYourLANUpdateCoordinator

WatchYourLANConfigEntry = ConfigEntry[WatchYourLANUpdateCoordinator]

# Define entity descriptions for each sensor type
ENTITY_DESCRIPTIONS = [
    SensorEntityDescription(
        key="online_status",
        translation_key="online_status",
    ),
    SensorEntityDescription(
        key="ip_address",
        translation_key="ip_address",
    ),
    SensorEntityDescription(
        key="iface",
        translation_key="iface",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the WatchYourLAN sensors."""
    coordinator: WatchYourLANUpdateCoordinator = entry.runtime_data

    entities: Sequence[SensorEntity | BinarySensorEntity] = [
        WatchYourLANOnlineStatusBinarySensor(coordinator, device)
        if description.key == "online_status"
        else WatchYourLANGenericSensor(coordinator, device, description)
        for device in coordinator.data
        for description in ENTITY_DESCRIPTIONS
    ]

    async_add_entities(entities)


class WatchYourLANOnlineStatusBinarySensor(
    CoordinatorEntity[WatchYourLANUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor to represent online/offline status."""

    def __init__(
        self,
        coordinator: WatchYourLANUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the binary sensor for online/offline state."""
        super().__init__(coordinator)
        self.device = device
        self._attr_unique_id = f"{self.device.get('Mac')}_online_status"
        mac_address = self.device["Mac"]
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, mac_address)},
            name=self.device.get("Name")
            or f"WatchYourLAN {self.device.get('ID', 'Unknown')}",
            manufacturer=self.device.get("Hw", "Unknown Manufacturer"),
            model="WatchYourLAN Device",
        )

    @property
    def is_on(self) -> bool:
        """Return true if the device is online."""
        return self.device.get("Now", 0) == 1

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return (
            self.device.get("Name")
            or f"WatchYourLAN {self.device.get('ID', 'Unknown')} Online Status"
        )

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the class of this device, which is 'connectivity'."""
        return BinarySensorDeviceClass.CONNECTIVITY


class WatchYourLANGenericSensor(
    CoordinatorEntity[WatchYourLANUpdateCoordinator], SensorEntity
):
    """Generic WatchYourLAN sensor for different data points."""

    def __init__(
        self,
        coordinator: WatchYourLANUpdateCoordinator,
        device: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.device = device
        self.entity_description = description
        self._attr_unique_id = f"{self.device.get('ID')}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.device["Mac"])},
            name=self.device.get("Name")
            or f"WatchYourLAN {self.device.get('ID', 'Unknown')}",
            manufacturer=self.device.get("Hw", "Unknown Manufacturer"),
            model="WatchYourLAN Device",
        )

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor based on its description."""
        if self.entity_description.key == "online_status":
            return "Online" if self.device.get("Now", 0) == 1 else "Offline"
        return self.device.get(self._get_device_field_for_key(), "Unknown")

    def _get_device_field_for_key(self) -> str:
        """Map description key to the appropriate device field."""
        field_mapping = {
            "online_status": "Now",
            "ip_address": "IP",
            "mac_address": "Mac",
            "iface": "Iface",
        }
        return field_mapping.get(self.entity_description.key, "")
