"""Sensor platform for Atomberg water purifiers."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, override

from atomberg_api import DEVICE_TYPE_LOCK, DEVICE_TYPE_WATER_PURIFIER, AtombergDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfRatio
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import AtombergConfigEntry, AtombergCoordinator
from .entity import AtombergEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AtombergSensorDescription(SensorEntityDescription):
    """Describes an Atomberg sensor."""

    value_fn: Callable[[Any], float | str | datetime | None]


WATER_PURIFIER_SENSORS: tuple[AtombergSensorDescription, ...] = (
    AtombergSensorDescription(
        key="input_tds",
        translation_key="input_tds",
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value,
    ),
    AtombergSensorDescription(
        key="tank_tds",
        translation_key="tank_tds",
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value,
    ),
    AtombergSensorDescription(
        key="ts_epoch_seconds",
        translation_key="last_reported",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: (
            None if value is None else dt_util.utc_from_timestamp(value)
        ),
    ),
)


LOCK_SENSORS: tuple[AtombergSensorDescription, ...] = (
    AtombergSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value,
    ),
    AtombergSensorDescription(
        key="n_unlocks",
        translation_key="unlock_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
    ),
    AtombergSensorDescription(
        key="esp_fw_version",
        translation_key="firmware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtombergConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Atomberg sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        AtombergSensor(coordinator, device, description)
        for device_type, descriptions in (
            (DEVICE_TYPE_WATER_PURIFIER, WATER_PURIFIER_SENSORS),
            (DEVICE_TYPE_LOCK, LOCK_SENSORS),
        )
        for device in coordinator.devices_of_type(device_type)
        for description in descriptions
        if description.key in coordinator.data.get(device.device_id, {})
    )


class AtombergSensor(AtombergEntity, SensorEntity):
    """Water purifier sensor."""

    entity_description: AtombergSensorDescription

    def __init__(
        self,
        coordinator: AtombergCoordinator,
        device: AtombergDevice,
        description: AtombergSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | str | datetime | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self.device_state.get(self.entity_description.key)
        )
