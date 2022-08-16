"""Fully Kiosk Browser sensor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_MEGABYTES, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="batteryLevel",
        name="Battery Level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(key="screenOrientation", name="Screen Orientation"),
    SensorEntityDescription(
        key="foregroundApp",
        name="Foreground App",
    ),
    SensorEntityDescription(key="currentPage", name="Current Page"),
    SensorEntityDescription(
        key="wifiSignalLevel",
        name="WiFi Signal Level",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    ),
    SensorEntityDescription(
        key="internalStorageFreeSpace",
        name="Internal Storage Free Space",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
    ),
    SensorEntityDescription(
        key="internalStorageTotalSpace",
        name="Internal Storage Total Space",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
    ),
    SensorEntityDescription(
        key="ramFreeMemory",
        name="RAM Free Memory",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
    ),
    SensorEntityDescription(
        key="ramTotalMemory",
        name="RAM Total Memory",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
    ),
)

STORAGE_SENSORS = [
    "internalStorageFreeSpace",
    "internalStorageTotalSpace",
    "ramFreeMemory",
    "ramTotalMemory",
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser sensor."""
    coordinator: FullyKioskDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        FullySensor(coordinator, description)
        for description in SENSORS
        if description.key in coordinator.data
    )


class FullySensor(FullyKioskEntity, SensorEntity):
    """Representation of a Fully Kiosk Browser sensor."""

    def __init__(
        self,
        coordinator: FullyKioskDataUpdateCoordinator,
        sensor: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        self.entity_description = sensor
        self._sensor = sensor.key
        self.coordinator = coordinator

        self._attr_unique_id = f"{coordinator.data['deviceID']}-{sensor.key}"

        super().__init__(coordinator)

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        if self._sensor in STORAGE_SENSORS:
            return round(self.coordinator.data[self._sensor] * 0.000001, 1)

        return self.coordinator.data.get(self._sensor)
