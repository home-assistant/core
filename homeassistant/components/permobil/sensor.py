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
    ENDPOINT_LOOKUP,
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
    item: str


@dataclass
class PermobilSensorEntityDescription(
    SensorEntityDescription, PermobilRequiredKeysMixin
):
    """Describes Permobil sensor entity."""


SENSOR_DESCRIPTIONS: tuple[PermobilSensorEntityDescription, ...] = (
    PermobilSensorEntityDescription(
        value_fn=lambda x: x,
        item=BATTERY_STATE_OF_CHARGE,
        key="state_of_charge",
        name="Permobil Battery Charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda x: x,
        item=BATTERY_STATE_OF_HEALTH,
        key="state_of_health",
        name="Permobil Battery Health",
        icon="mdi:battery-heart-variant",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda x: x,
        item=BATTERY_CHARGE_TIME_LEFT,
        key="charge_time_left",
        name="Permobil Charge Time Left",
        icon="mdi:battery-clock",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda x: x,
        item=BATTERY_DISTANCE_LEFT,
        key="distance_left",
        name="Permobil Distance Left",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda x: x,
        item=BATTERY_INDOOR_DRIVE_TIME,
        key="indoor_drive_time",
        name="Permobil Indoor Drive Time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda x: x * BATTERY_ASSUMED_VOLTAGE,
        item=BATTERY_MAX_AMPERE_HOURS,
        key="max_watt_hours",
        name="Permobil Battery Max Watt Hours",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda x: x * BATTERY_ASSUMED_VOLTAGE,
        item=BATTERY_AMPERE_HOURS_LEFT,
        key="watt_hours_left",
        name="Permobil Watt Hours Left",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda x: x,
        item=BATTERY_MAX_DISTANCE_LEFT,
        key="max_distance_left",
        name="Permobil Full Charge Distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda x: x,
        item=USAGE_DISTANCE,
        key="usage_distance",
        name="Permobil Distance Traveled",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda x: x,
        item=USAGE_ADJUSTMENTS,
        key="usage_adjustments",
        name="Permobil Number of Adjustments",
        native_unit_of_measurement="adjustments",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PermobilSensorEntityDescription(
        value_fn=lambda x: x,
        item=RECORDS_SEATING,
        key="record_adjustments",
        name="Permobil Record Number of Adjustments",
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

    _attr_suggested_display_precision: int = 0

    def __init__(
        self,
        coordinator: MyPermobilCoordinator,
        description: PermobilSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)
        self._coordinator = coordinator
        self.entity_description = description
        self._attr_name = str(description.name)
        self._item = description.item
        self._value_fn = description.value_fn
        self._attr_unique_id = f"{coordinator.p_api.email}_{self._item}"

    @property
    def native_value(self) -> float | None:
        """Return the value of the sensor."""
        endpoint = ENDPOINT_LOOKUP[self._item]
        data = self._coordinator.data.get(endpoint, {}).get(self._item)

        return self._value_fn(data)
