"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
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
    ENDPOINT_BATTERY_INFO,
    ENDPOINT_DAILY_USAGE,
    ENDPOINT_VA_USAGE_RECORDS,
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
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BATTERY_ASSUMED_VOLTAGE, DOMAIN
from .coordinator import MyPermobilCoordinator


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""


_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=50)


@dataclass
class PermobilRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Any], Any]


@dataclass
class PermobilSensorEntityDescription(
    SensorEntityDescription, PermobilRequiredKeysMixin
):
    """Describes Permobil sensor entity."""


SENSOR_DESCRIPTIONS: tuple[PermobilSensorEntityDescription, ...] = (
    PermobilSensorEntityDescription(
        value_fn=lambda data: data[ENDPOINT_BATTERY_INFO][BATTERY_STATE_OF_CHARGE],
        key=BATTERY_STATE_OF_CHARGE,
        translation_key="state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda data: data[ENDPOINT_BATTERY_INFO][BATTERY_STATE_OF_HEALTH],
        key=BATTERY_STATE_OF_HEALTH,
        translation_key="state_of_health",
        icon="mdi:battery-heart-variant",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda data: data[ENDPOINT_BATTERY_INFO][BATTERY_CHARGE_TIME_LEFT],
        key=BATTERY_CHARGE_TIME_LEFT,
        translation_key="charge_time_left",
        icon="mdi:battery-clock",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda data: data[ENDPOINT_BATTERY_INFO][BATTERY_DISTANCE_LEFT],
        key=BATTERY_DISTANCE_LEFT,
        translation_key="distance_left",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda data: data[ENDPOINT_BATTERY_INFO][BATTERY_INDOOR_DRIVE_TIME],
        key=BATTERY_INDOOR_DRIVE_TIME,
        translation_key="indoor_drive_time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda data: data[ENDPOINT_BATTERY_INFO][BATTERY_MAX_AMPERE_HOURS]
        * BATTERY_ASSUMED_VOLTAGE,
        key=BATTERY_MAX_AMPERE_HOURS,
        translation_key="max_watt_hours",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda data: data[ENDPOINT_BATTERY_INFO][BATTERY_AMPERE_HOURS_LEFT]
        * BATTERY_ASSUMED_VOLTAGE,
        key=BATTERY_AMPERE_HOURS_LEFT,
        translation_key="watt_hours_left",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda data: data[ENDPOINT_BATTERY_INFO][BATTERY_MAX_DISTANCE_LEFT],
        key=BATTERY_MAX_DISTANCE_LEFT,
        translation_key="max_distance_left",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda data: data[ENDPOINT_DAILY_USAGE][USAGE_DISTANCE],
        key=USAGE_DISTANCE,
        translation_key="usage_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda data: data[ENDPOINT_DAILY_USAGE][USAGE_ADJUSTMENTS],
        key=USAGE_ADJUSTMENTS,
        translation_key="usage_adjustments",
        native_unit_of_measurement="adjustments",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda data: data[ENDPOINT_VA_USAGE_RECORDS][RECORDS_SEATING],
        key=RECORDS_SEATING,
        translation_key="record_adjustments",
        native_unit_of_measurement="adjustments",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors from a config entry created in the integrations UI."""

    # create the API object from the config
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        PermobilSensor(coordinator=coordinator, description=description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities, update_before_add=True)


class PermobilSensor(CoordinatorEntity[MyPermobilCoordinator], SensorEntity):
    """Representation of a Sensor.

    This implements the common functions of all sensors.
    """

    _attr_has_entity_name = True
    _attr_suggested_display_precision = 0
    entity_description: PermobilSensorEntityDescription

    def __init__(
        self,
        coordinator: MyPermobilCoordinator,
        description: PermobilSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.p_api.email}_{self.entity_description.key}"
        )

    @property
    def native_value(self) -> float | None:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
