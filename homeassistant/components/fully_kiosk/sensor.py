"""Fully Kiosk Browser sensor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity


def round_storage(value: int) -> float:
    """Convert storage values from bytes to megabytes."""
    return round(value * 0.000001, 1)


@dataclass
class FullySensorEntityDescription(SensorEntityDescription):
    """Fully Kiosk Browser sensor description."""

    state_fn: Callable[[int], float] | None = None


SENSORS: tuple[FullySensorEntityDescription, ...] = (
    FullySensorEntityDescription(
        key="batteryLevel",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FullySensorEntityDescription(
        key="screenOrientation",
        name="Screen orientation",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FullySensorEntityDescription(
        key="foregroundApp",
        name="Foreground app",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FullySensorEntityDescription(
        key="currentPage",
        name="Current page",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FullySensorEntityDescription(
        key="internalStorageFreeSpace",
        name="Internal storage free space",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        state_fn=round_storage,
    ),
    FullySensorEntityDescription(
        key="internalStorageTotalSpace",
        name="Internal storage total space",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        state_fn=round_storage,
    ),
    FullySensorEntityDescription(
        key="ramFreeMemory",
        name="Free memory",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        state_fn=round_storage,
    ),
    FullySensorEntityDescription(
        key="ramTotalMemory",
        name="Total memory",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        state_fn=round_storage,
    ),
)


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

    entity_description: FullySensorEntityDescription

    def __init__(
        self,
        coordinator: FullyKioskDataUpdateCoordinator,
        sensor: FullySensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        self.entity_description = sensor

        self._attr_unique_id = f"{coordinator.data['deviceID']}-{sensor.key}"

        super().__init__(coordinator)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if (value := self.coordinator.data.get(self.entity_description.key)) is None:
            return None

        if self.entity_description.state_fn is not None:
            return self.entity_description.state_fn(value)

        return value  # type: ignore[no-any-return]
