"""Sensor platform for CentriConnect/MyPropane API integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
    UnitOfTemperature,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CentriConnectConfigEntry, CentriConnectCoordinator
from .entity import CentriConnectBaseEntity

# Coordinator is used to centralize the data updates.
PARALLEL_UPDATES = 0


_ALERT_STATUS_VALUES = {
    "No Alert": "no_alert",
    "Low Level": "low_level",
    "Critical Level": "critical_level",
}


class CentriConnectSensorType(StrEnum):
    """Enumerates CentriConnect sensor types exposed by the device."""

    ALERT_STATUS = "alert_status"
    ALTITUDE = "altitude"
    BATTERY_LEVEL = "battery_level"
    BATTERY_VOLTAGE = "battery_voltage"
    DEVICE_TEMPERATURE = "device_temperature"
    LAST_POST_TIME = "last_post_time"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    LTE_SIGNAL_LEVEL = "lte_signal_level"
    LTE_SIGNAL_STRENGTH = "lte_signal_strength"
    NEXT_POST_TIME = "next_post_time"
    SOLAR_LEVEL = "solar_level"
    SOLAR_VOLTAGE = "solar_voltage"
    TANK_LEVEL = "tank_level"
    TANK_REMAINING_VOLUME = "tank_remaining_volume"
    TANK_SIZE = "tank_size"


@dataclass(frozen=True, kw_only=True)
class CentriConnectSensorEntityDescription(SensorEntityDescription):
    """Description of a CentriConnect sensor entity."""

    key: CentriConnectSensorType
    value_fn: Callable[[CentriConnectCoordinator], StateType | datetime | None]


ENTITIES: tuple[CentriConnectSensorEntityDescription, ...] = (
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.ALERT_STATUS,
        translation_key=CentriConnectSensorType.ALERT_STATUS,
        device_class=SensorDeviceClass.ENUM,
        options=list(_ALERT_STATUS_VALUES.values()),
        value_fn=lambda coord: _ALERT_STATUS_VALUES.get(coord.data.alert_status),
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.ALTITUDE,
        translation_key=CentriConnectSensorType.ALTITUDE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda coord: coord.data.altitude,
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.BATTERY_LEVEL,
        translation_key=CentriConnectSensorType.BATTERY_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coord: coord.data.battery_level,
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.BATTERY_VOLTAGE,
        translation_key=CentriConnectSensorType.BATTERY_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=lambda coord: coord.data.battery_voltage,
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.DEVICE_TEMPERATURE,
        translation_key=CentriConnectSensorType.DEVICE_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda coord: coord.data.device_temperature,
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.LTE_SIGNAL_LEVEL,
        translation_key=CentriConnectSensorType.LTE_SIGNAL_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=lambda coord: coord.data.lte_signal_level,
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.LTE_SIGNAL_STRENGTH,
        translation_key=CentriConnectSensorType.LTE_SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda coord: coord.data.lte_signal_strength,
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.SOLAR_LEVEL,
        translation_key=CentriConnectSensorType.SOLAR_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=lambda coord: coord.data.solar_level,
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.SOLAR_VOLTAGE,
        translation_key=CentriConnectSensorType.SOLAR_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=lambda coord: coord.data.solar_voltage,
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.TANK_LEVEL,
        translation_key=CentriConnectSensorType.TANK_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coord: coord.data.tank_level,
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.TANK_REMAINING_VOLUME,
        translation_key=CentriConnectSensorType.TANK_REMAINING_VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        suggested_display_precision=2,
        value_fn=lambda coord: (
            coord.data.tank_remaining_volume
            if coord.device_info.tank_size_unit == "Gallons"
            else None
        ),
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.TANK_REMAINING_VOLUME,
        translation_key=CentriConnectSensorType.TANK_REMAINING_VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        suggested_display_precision=2,
        value_fn=lambda coord: (
            coord.data.tank_remaining_volume
            if coord.device_info.tank_size_unit == "Liters"
            else None
        ),
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.TANK_SIZE,
        translation_key=CentriConnectSensorType.TANK_SIZE,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        suggested_display_precision=2,
        value_fn=lambda coord: (
            coord.device_info.tank_size
            if (coord.device_info.tank_size_unit == "Gallons")
            else None
        ),
    ),
    CentriConnectSensorEntityDescription(
        key=CentriConnectSensorType.TANK_SIZE,
        translation_key=CentriConnectSensorType.TANK_SIZE,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        suggested_display_precision=2,
        value_fn=lambda coord: (
            coord.device_info.tank_size
            if (coord.device_info.tank_size_unit == "Liters")
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CentriConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up CentriConnect sensor entities from a config entry."""
    async_add_entities(
        CentriConnectSensor(entry.runtime_data, description)
        for description in ENTITIES
        if description.value_fn(entry.runtime_data) is not None
    )


class CentriConnectSensor(CentriConnectBaseEntity, SensorEntity):
    """Representation of a CentriConnect sensor entity."""

    entity_description: CentriConnectSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator)
