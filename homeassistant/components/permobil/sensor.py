"""Platform for sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from mypermobil import (
    BATTERY_AMPERE_HOURS_LEFT,
    BATTERY_CHARGE_TIME_LEFT,
    BATTERY_DISTANCE_LEFT,
    BATTERY_INDOOR_DRIVE_TIME,
    BATTERY_MAX_AMPERE_HOURS,
    BATTERY_MAX_DISTANCE_LEFT,
    BATTERY_STATE_OF_CHARGE,
    BATTERY_STATE_OF_HEALTH,
    RECORDS_DISTANCE,
    RECORDS_DISTANCE_UNIT,
    RECORDS_SEATING,
    USAGE_ADJUSTMENTS,
    USAGE_DISTANCE,
)

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BATTERY_ASSUMED_VOLTAGE, DOMAIN, KM, MILES
from .coordinator import MyPermobilCoordinator
from .entity import PermobilEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PermobilSensorEntityDescription(SensorEntityDescription):
    """Describes Permobil sensor entity."""

    value_fn: Callable[[Any], float | int]
    available_fn: Callable[[Any], bool]


SENSOR_DESCRIPTIONS: tuple[PermobilSensorEntityDescription, ...] = (
    PermobilSensorEntityDescription(
        # Current battery as a percentage
        value_fn=lambda data: data.battery[BATTERY_STATE_OF_CHARGE[0]],
        available_fn=lambda data: BATTERY_STATE_OF_CHARGE[0] in data.battery,
        key="state_of_charge",
        translation_key="state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        # Current battery health as a percentage of original capacity
        value_fn=lambda data: data.battery[BATTERY_STATE_OF_HEALTH[0]],
        available_fn=lambda data: BATTERY_STATE_OF_HEALTH[0] in data.battery,
        key="state_of_health",
        translation_key="state_of_health",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        # Time until fully charged (displays 0 if not charging)
        value_fn=lambda data: data.battery[BATTERY_CHARGE_TIME_LEFT[0]],
        available_fn=lambda data: BATTERY_CHARGE_TIME_LEFT[0] in data.battery,
        key="charge_time_left",
        translation_key="charge_time_left",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
    ),
    PermobilSensorEntityDescription(
        # Distance possible on current change (km)
        value_fn=lambda data: data.battery[BATTERY_DISTANCE_LEFT[0]],
        available_fn=lambda data: BATTERY_DISTANCE_LEFT[0] in data.battery,
        key="distance_left",
        translation_key="distance_left",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    PermobilSensorEntityDescription(
        # Drive time possible on current charge
        value_fn=lambda data: data.battery[BATTERY_INDOOR_DRIVE_TIME[0]],
        available_fn=lambda data: BATTERY_INDOOR_DRIVE_TIME[0] in data.battery,
        key="indoor_drive_time",
        translation_key="indoor_drive_time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
    ),
    PermobilSensorEntityDescription(
        # Watt hours the battery can store given battery health
        value_fn=lambda data: data.battery[BATTERY_MAX_AMPERE_HOURS[0]]
        * BATTERY_ASSUMED_VOLTAGE,
        available_fn=lambda data: BATTERY_MAX_AMPERE_HOURS[0] in data.battery,
        key="max_watt_hours",
        translation_key="max_watt_hours",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        # Current amount of watt hours in battery
        value_fn=lambda data: data.battery[BATTERY_AMPERE_HOURS_LEFT[0]]
        * BATTERY_ASSUMED_VOLTAGE,
        available_fn=lambda data: BATTERY_AMPERE_HOURS_LEFT[0] in data.battery,
        key="watt_hours_left",
        translation_key="watt_hours_left",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        # Distance that can be traveled with full charge given battery health (km)
        value_fn=lambda data: data.battery[BATTERY_MAX_DISTANCE_LEFT[0]],
        available_fn=lambda data: BATTERY_MAX_DISTANCE_LEFT[0] in data.battery,
        key="max_distance_left",
        translation_key="max_distance_left",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    PermobilSensorEntityDescription(
        # Distance traveled today monotonically increasing, resets every 24h (km)
        value_fn=lambda data: data.daily_usage[USAGE_DISTANCE[0]],
        available_fn=lambda data: USAGE_DISTANCE[0] in data.daily_usage,
        key="usage_distance",
        translation_key="usage_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    PermobilSensorEntityDescription(
        # Number of adjustments monotonically increasing, resets every 24h
        value_fn=lambda data: data.daily_usage[USAGE_ADJUSTMENTS[0]],
        available_fn=lambda data: USAGE_ADJUSTMENTS[0] in data.daily_usage,
        key="usage_adjustments",
        translation_key="usage_adjustments",
        native_unit_of_measurement="adjustments",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    PermobilSensorEntityDescription(
        # Largest number of adjustemnts in a single 24h period, monotonically increasing, never resets
        value_fn=lambda data: data.records[RECORDS_SEATING[0]],
        available_fn=lambda data: RECORDS_SEATING[0] in data.records,
        key="record_adjustments",
        translation_key="record_adjustments",
        native_unit_of_measurement="adjustments",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    PermobilSensorEntityDescription(
        # Record of largest distance travelled in a day, monotonically increasing, never resets
        value_fn=lambda data: data.records[RECORDS_DISTANCE[0]],
        available_fn=lambda data: RECORDS_DISTANCE[0] in data.records,
        key="record_distance",
        translation_key="record_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

DISTANCE_UNITS: dict[Any, UnitOfLength] = {
    KM: UnitOfLength.KILOMETERS,
    MILES: UnitOfLength.MILES,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors from a config entry created in the integrations UI."""

    coordinator: MyPermobilCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        PermobilSensor(coordinator=coordinator, description=description)
        for description in SENSOR_DESCRIPTIONS
    )


class PermobilSensor(PermobilEntity, SensorEntity):
    """Representation of a Sensor.

    This implements the common functions of all sensors.
    """

    _attr_suggested_display_precision = 0
    entity_description: PermobilSensorEntityDescription

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor."""
        if self.entity_description.key == "record_distance":
            return DISTANCE_UNITS.get(
                self.coordinator.data.records[RECORDS_DISTANCE_UNIT[0]]
            )
        return self.entity_description.native_unit_of_measurement

    @property
    def available(self) -> bool:
        """Return True if the sensor has value."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )

    @property
    def native_value(self) -> float | int:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
