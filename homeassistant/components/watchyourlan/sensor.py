"""Support for the WatchYourLAN service."""

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WatchYourLANConfigEntry
from .coordinator import WatchYourLANUpdateCoordinator

# Define entity descriptions for each sensor type
ENTITY_DESCRIPTIONS = [
    SensorEntityDescription(
        key="IP",
        translation_key="ip_address",
    ),
    SensorEntityDescription(
        key="Iface",
        translation_key="iface",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WatchYourLANConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WatchYourLAN sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        WatchYourLANGenericSensor(coordinator, device, description)
        for device in coordinator.data
        for description in ENTITY_DESCRIPTIONS
    )


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
        self._attr_unique_id = f"{self.device.get('Mac')}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.device["Mac"])},
            default_name=(
                self.device.get("Name")
                or f"WatchYourLAN {self.device.get('ID', 'Unknown')}"
            ),
            default_manufacturer=self.device.get("Hw", None),
        )

    @property
    def native_value(self) -> str | None:
        """Return the native value of the sensor based on its description."""

        return self.device.get(self.entity_description.key)
