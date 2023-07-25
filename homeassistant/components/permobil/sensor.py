"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from mypermobil import (
    BATTERY_AMPERE_HOURS_LEFT,
    BATTERY_CHARGE_TIME_LEFT,
    BATTERY_DISTANCE_LEFT,
    BATTERY_INDOOR_DRIVE_TIME,
    BATTERY_MAX_DISTANCE_LEFT,
    BATTERY_STATE_OF_CHARGE,
    BATTERY_STATE_OF_HEALTH,
    ENDPOINT_LOOKUP,
    RECORDS_DISTANCE,
    RECORDS_SEATING,
    USAGE_ADJUSTMENTS,
    USAGE_DISTANCE,
)

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
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

from .const import COORDINATOR, DOMAIN
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors from a config entry created in the integrations UI."""

    # create the API object from the config
    coordinator = hass.data[DOMAIN][COORDINATOR][config_entry.entry_id]
    sensors = [
        PermobilDistanceLeftSensor(coordinator),
        PermobilMaxDistanceLeftSensor(coordinator),
        PermobilUsageDistanceSensor(coordinator),
        PermobilRecordDistanceSensor(coordinator),
        PermobilStateOfChargeSensor(coordinator),
        PermobilStateOfHealthSensor(coordinator),
        # PermobilChargingSensor(coordinator),
        PermobilChargeTimeLeftSensor(coordinator),
        PermobilIndoorDriveTimeSensor(coordinator),
        PermobilMaxWattHoursSensor(coordinator),
        PermobilWattHoursLeftSensor(coordinator),
        PermobilUsageAdjustmentsSensor(coordinator),
        PermobilRecordAdjustmentsSensor(coordinator),
    ]

    async_add_entities(sensors, update_before_add=True)


class PermobilGenericSensor(CoordinatorEntity[MyPermobilCoordinator], SensorEntity):
    """Representation of a Sensor.

    This implements the common functions of all sensors.
    """

    _attr_name = "Generic Sensor"
    _attr_suggested_display_precision: int | None = 0
    _item: str | None = None

    def __init__(self, coordinator: MyPermobilCoordinator) -> None:
        """Initialize the sensor.

        item: The item to request from the API.
        """
        super().__init__(coordinator=coordinator)
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.p_api.email}_{self._item}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        data = None
        if self._item in ENDPOINT_LOOKUP:
            endpoint = ENDPOINT_LOOKUP[self._item]
            data = self._coordinator.data[endpoint][self._item]

        return data


class PermobilStateOfChargeSensor(PermobilGenericSensor):
    """Batter percentage sensor."""

    _attr_name = "Permobil Battery Charge"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _item = BATTERY_STATE_OF_CHARGE


class PermobilStateOfHealthSensor(PermobilGenericSensor):
    """Battery health sensor."""

    _attr_name = "Permobil Battery Health"
    _attr_icon = "mdi:battery-heart-variant"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _item = BATTERY_STATE_OF_HEALTH


# class PermobilChargingSensor(BinarySensorEntity):
#  """Battery charging sensor.

#    This is a binary sensor because it can only be on or off.
#   """

#   _attr_name = "Permobil is Charging"
#   _attr_icon = "mdi:battery-unknown"
#   _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
#   _item = BATTERY_CHARGING

#   def __init__(self, permobil: MyPermobil) -> None:
#   """Initialize the sensor.
#
#        this is a binary sensor and has a different constructor.
#       """
#     super().__init__()
#      self._permobil = permobil
#     self._item = BATTERY_CHARGING

# async def async_update(self) -> None:
#      """Get charging status."""
#    try:
#      self._attr_is_on = bool(await self._permobil.request_item(self._item))
#   except (MyPermobilClientException, MyPermobilAPIException):
# if we can't get the charging status, assume it is not charging
#     self._attr_is_on = False


class PermobilChargeTimeLeftSensor(PermobilGenericSensor):
    """Battery charge time left sensor."""

    _attr_name = "Permobil Charge Time Left"
    _attr_icon = "mdi:battery-clock"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _item = BATTERY_CHARGE_TIME_LEFT


class PermobilDistanceLeftSensor(PermobilGenericSensor):
    """Battery distance left sensor."""

    _attr_name = "Permobil Distance Left"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _item = BATTERY_DISTANCE_LEFT


class PermobilIndoorDriveTimeSensor(PermobilGenericSensor):
    """Battery indoor drive time sensor."""

    _attr_name = "Permobil Indoor Drive Time"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _item = BATTERY_INDOOR_DRIVE_TIME


class PermobilMaxWattHoursSensor(PermobilGenericSensor):
    """Battery max watt hours sensor.

    converted from ampere hours by multiplying with voltage.
    """

    _attr_name = "Permobil Battery Max Watt Hours"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_value: float | None = None


class PermobilWattHoursLeftSensor(PermobilGenericSensor):
    """Battery ampere hours left sensor.

    converted from ampere hours by multiplying with voltage.
    """

    _attr_name = "Permobil Watt Hours Left"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_value: float | None = None
    _item = BATTERY_AMPERE_HOURS_LEFT


class PermobilMaxDistanceLeftSensor(PermobilGenericSensor):
    """Battery max distance left sensor."""

    _attr_name = "Permobil Full Charge Distance"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _item = BATTERY_MAX_DISTANCE_LEFT


class PermobilUsageDistanceSensor(PermobilGenericSensor):
    """usage distance sensor."""

    _attr_name = "Permobil Distance Traveled"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _item = USAGE_DISTANCE


class PermobilUsageAdjustmentsSensor(PermobilGenericSensor):
    """usage adjustments sensor."""

    _attr_name = "Permobil Number of Adjustments"
    _attr_native_unit_of_measurement = "adjustments"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _item = USAGE_ADJUSTMENTS


class PermobilRecordDistanceSensor(PermobilGenericSensor):
    """record distance sensor."""

    _attr_name = "Permobil Record Distance Traveled"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _item = RECORDS_DISTANCE


class PermobilRecordAdjustmentsSensor(PermobilGenericSensor):
    """record adjustments sensor."""

    _attr_name = "Permobil Record Number of Adjustments"
    _attr_native_unit_of_measurement = "adjustments"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _item = RECORDS_SEATING
