"""Contains sensors exposed by the Starlink integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfDataRate,
    UnitOfEnergy,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import now

from .coordinator import StarlinkConfigEntry, StarlinkData
from .entity import StarlinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: StarlinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all sensors for this entry."""
    async_add_entities(
        StarlinkSensorEntity(config_entry.runtime_data, description)
        for description in SENSORS
    )

    async_add_entities(
        StarlinkRestoreSensor(config_entry.runtime_data, description)
        for description in RESTORE_SENSORS
    )


@dataclass(frozen=True, kw_only=True)
class StarlinkSensorEntityDescription(SensorEntityDescription):
    """Describes a Starlink sensor entity."""

    value_fn: Callable[[StarlinkData], datetime | StateType]


class StarlinkSensorEntity(StarlinkEntity, SensorEntity):
    """A SensorEntity for Starlink devices. Handles creating unique IDs."""

    entity_description: StarlinkSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Calculate the sensor value from the entity description."""
        return self.entity_description.value_fn(self.coordinator.data)


class StarlinkRestoreSensor(StarlinkSensorEntity, RestoreSensor):
    """A RestoreSensorEntity for Starlink devices. Handles creating unique IDs."""

    _attr_native_value: int | float = 0

    @property
    def native_value(self) -> StateType | datetime:
        """Calculate the sensor value from current value and the entity description."""
        native_value = super().native_value
        assert isinstance(native_value, (int, float))
        return self._attr_native_value + native_value

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        if (
            last_sensor_data := await self.async_get_last_sensor_data()
        ) is not None and (
            last_native_value := last_sensor_data.native_value
        ) is not None:
            assert isinstance(last_native_value, (int, float))
            self._attr_native_value = last_native_value


SENSORS: tuple[StarlinkSensorEntityDescription, ...] = (
    StarlinkSensorEntityDescription(
        key="ping",
        translation_key="ping",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_display_precision=0,
        value_fn=lambda data: data.status["pop_ping_latency_ms"],
    ),
    StarlinkSensorEntityDescription(
        key="azimuth",
        translation_key="azimuth",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DEGREE,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=lambda data: data.status["direction_azimuth"],
    ),
    StarlinkSensorEntityDescription(
        key="elevation",
        translation_key="elevation",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DEGREE,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=lambda data: data.status["direction_elevation"],
    ),
    StarlinkSensorEntityDescription(
        key="uplink_throughput",
        translation_key="uplink_throughput",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BITS_PER_SECOND,
        suggested_display_precision=3,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        value_fn=lambda data: data.status["uplink_throughput_bps"],
    ),
    StarlinkSensorEntityDescription(
        key="downlink_throughput",
        translation_key="downlink_throughput",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BITS_PER_SECOND,
        suggested_display_precision=3,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        value_fn=lambda data: data.status["downlink_throughput_bps"],
    ),
    StarlinkSensorEntityDescription(
        key="last_boot_time",
        translation_key="last_boot_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: now() - timedelta(seconds=data.status["uptime"]),
    ),
    StarlinkSensorEntityDescription(
        key="ping_drop_rate",
        translation_key="ping_drop_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.status["pop_ping_drop_rate"] * 100,
    ),
    StarlinkSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.consumption["latest_power"],
    ),
)
RESTORE_SENSORS: tuple[StarlinkSensorEntityDescription, ...] = (
    StarlinkSensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=lambda data: data.consumption["total_energy"],
    ),
    StarlinkSensorEntityDescription(
        key="download",
        translation_key="download",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=3,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        value_fn=lambda data: data.usage["download_usage"],
    ),
    StarlinkSensorEntityDescription(
        key="upload",
        translation_key="upload",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=3,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        value_fn=lambda data: data.usage["upload_usage"],
    ),
)
