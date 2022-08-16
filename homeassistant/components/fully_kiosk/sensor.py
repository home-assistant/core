"""Fully Kiosk Browser sensor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
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
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="screenOrientation",
        name="Screen orientation",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="foregroundApp",
        name="Foreground app",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="currentPage",
        name="Current page",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="internalStorageFreeSpace",
        name="Internal storage free space",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="internalStorageTotalSpace",
        name="Internal storage total space",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ramFreeMemory",
        name="Free memory",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ramTotalMemory",
        name="Total memory",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
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

        self._attr_unique_id = f"{coordinator.data['deviceID']}-{sensor.key}"

        super().__init__(coordinator)

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if (value := self.coordinator.data.get(self.entity_description.key)) is None:
            return None

        if self.entity_description.key in STORAGE_SENSORS:
            return round(value * 0.000001, 1)

        return value
