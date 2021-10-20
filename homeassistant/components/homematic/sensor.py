"""Support for HomeMatic sensors."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_MILLIAMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    FREQUENCY_HERTZ,
    LENGTH_MILLIMETERS,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    VOLUME_CUBIC_METERS,
)

from .const import ATTR_DISCOVER_DEVICES
from .entity import HMDevice

_LOGGER = logging.getLogger(__name__)

HM_STATE_HA_CAST = {
    "IPGarage": {0: "closed", 1: "open", 2: "ventilation", 3: None},
    "RotaryHandleSensor": {0: "closed", 1: "tilted", 2: "open"},
    "RotaryHandleSensorIP": {0: "closed", 1: "tilted", 2: "open"},
    "WaterSensor": {0: "dry", 1: "wet", 2: "water"},
    "CO2Sensor": {0: "normal", 1: "added", 2: "strong"},
    "IPSmoke": {0: "off", 1: "primary", 2: "intrusion", 3: "secondary"},
    "RFSiren": {
        0: "disarmed",
        1: "extsens_armed",
        2: "allsens_armed",
        3: "alarm_blocked",
    },
    "IPLockDLD": {0: None, 1: "locked", 2: "unlocked"},
}


SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "HUMIDITY_MEASUREMENT": SensorEntityDescription(
        key="HUMIDITY_MEASUREMENT",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "TEMPERATURE_MEASUREMENT": SensorEntityDescription(
        key="TEMPERATURE_MEASUREMENT",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "ILLUMINATION_MEASUREMENT": SensorEntityDescription(
        key="ILLUMINATION_MEASUREMENT",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "ILLUMINATION_TOTAL": SensorEntityDescription(
        key="ILLUMINATION_TOTAL",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_TOTAL,
    ),
    "POWER_MEASUREMENT": SensorEntityDescription(
        key="POWER_MEASUREMENT",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "CURRENT_MEASUREMENT": SensorEntityDescription(
        key="CURRENT_MEASUREMENT",
        native_unit_of_measurement=ELECTRIC_CURRENT_MILLIAMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "CONCENTRATION_MEASUREMENT": SensorEntityDescription(
        key="CONCENTRATION_MEASUREMENT",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=DEVICE_CLASS_CO2,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "ENERGY_COUNTER_TOTAL_INCREASING": SensorEntityDescription(
        key="ENERGY_COUNTER_TOTAL_INCREASING",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "VOLTAGE_MEASUREMENT": SensorEntityDescription(
        key="VOLTAGE_MEASUREMENT",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "GAS_POWER_MEASUREMENT": SensorEntityDescription(
        key="GAS_POWER_MEASUREMENT",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=DEVICE_CLASS_GAS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "GAS_ENERGY_COUNTER_TOTAL_INCREASING": SensorEntityDescription(
        key="GAS_ENERGY_COUNTER_TOTAL_INCREASING",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=DEVICE_CLASS_GAS,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "RAIN_COUNTER": SensorEntityDescription(
        key="RAIN_COUNTER",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
    ),
    "WIND_SPEED": SensorEntityDescription(
        key="WIND_SPEED",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        icon="mdi:weather-windy",
    ),
    "WIND_DIRECTION": SensorEntityDescription(
        key="WIND_DIRECTION",
        native_unit_of_measurement=DEGREE,
    ),
    "SUNSHINEDURATION": SensorEntityDescription(
        key="SUNSHINEDURATION",
        native_unit_of_measurement="#",
    ),
    "AIR_PRESSURE_MEASUREMENT": SensorEntityDescription(
        key="AIR_PRESSURE",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "FREQUENCY": SensorEntityDescription(
        key="FREQUENCY",
        native_unit_of_measurement=FREQUENCY_HERTZ,
    ),
    "VALUE": SensorEntityDescription(
        key="VALUE",
        native_unit_of_measurement="#",
    ),
    "VALVE_STATE": SensorEntityDescription(
        key="VALVE_STATE",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "CARRIER_SENSE_LEVEL": SensorEntityDescription(
        key="CARRIER_SENSE_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "DUTY_CYCLE_LEVEL": SensorEntityDescription(
        key="DUTY_CYCLE_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "BRIGHTNESS": SensorEntityDescription(
        key="BRIGHTNESS", native_unit_of_measurement="#", icon="mdi:invert-colors"
    ),
}

SENSOR_TYPES: dict[str, SensorEntityDescription | None] = {
    "ACTUAL_TEMPERATURE": SENSOR_DESCRIPTIONS.get("TEMPERATURE_MEASUREMENT"),
    "TEMPERATURE": SENSOR_DESCRIPTIONS.get("TEMPERATURE_MEASUREMENT"),
    "LUX": SENSOR_DESCRIPTIONS.get("ILLUMINATION_MEASUREMENT"),
    "CURRENT_ILLUMINATION": SENSOR_DESCRIPTIONS.get("ILLUMINATION_MEASUREMENT"),
    "ILLUMINATION": SENSOR_DESCRIPTIONS.get("ILLUMINATION_MEASUREMENT"),
    "AVERAGE_ILLUMINATION": SENSOR_DESCRIPTIONS.get("ILLUMINATION_TOTAL"),
    "LOWEST_ILLUMINATION": SENSOR_DESCRIPTIONS.get("ILLUMINATION_TOTAL"),
    "HIGHEST_ILLUMINATION": SENSOR_DESCRIPTIONS.get("ILLUMINATION_TOTAL"),
    "POWER": SENSOR_DESCRIPTIONS.get("POWER_MEASUREMENT"),
    "IEC_POWER": SENSOR_DESCRIPTIONS.get("POWER_MEASUREMENT"),
    "CURRENT": SENSOR_DESCRIPTIONS.get("CURRENT_MEASUREMENT"),
    "CONCENTRATION": SENSOR_DESCRIPTIONS.get("CONCENTRATION_MEASUREMENT"),
    "ENERGY_COUNTER": SENSOR_DESCRIPTIONS.get("ENERGY_COUNTER_TOTAL_INCREASING"),
    "IEC_ENERGY_COUNTER": SENSOR_DESCRIPTIONS.get("ENERGY_COUNTER_TOTAL_INCREASING"),
    "VOLTAGE": SENSOR_DESCRIPTIONS.get("VOLTAGE_MEASUREMENT"),
    "GAS_POWER": SENSOR_DESCRIPTIONS.get("GAS_POWER_MEASUREMENT"),
    "GAS_ENERGY_COUNTER": SENSOR_DESCRIPTIONS.get(
        "GAS_ENERGY_COUNTER_TOTAL_INCREASING"
    ),
    "RAIN_COUNTER": SENSOR_DESCRIPTIONS.get("RAIN_COUNTER"),
    "WIND_SPEED": SENSOR_DESCRIPTIONS.get("WIND_SPEED"),
    "WIND_DIRECTION": SENSOR_DESCRIPTIONS.get("WIND_DIRECTION"),
    "WIND_DIRECTION_RANGE": SENSOR_DESCRIPTIONS.get("WIND_DIRECTION"),
    "SUNSHINEDURATION": SENSOR_DESCRIPTIONS.get("SUNSHINEDURATION"),
    "AIR_PRESSURE": SENSOR_DESCRIPTIONS.get("AIR_PRESSURE_MEASUREMENT"),
    "FREQUENCY": SENSOR_DESCRIPTIONS.get("FREQUENCY"),
    "VALUE": SENSOR_DESCRIPTIONS.get("VALUE"),
    "VALVE_STATE": SENSOR_DESCRIPTIONS.get("VALVE_STATE"),
    "CARRIER_SENSE_LEVEL": SENSOR_DESCRIPTIONS.get("CARRIER_SENSE_LEVEL"),
    "DUTY_CYCLE_LEVEL": SENSOR_DESCRIPTIONS.get("DUTY_CYCLE_LEVEL"),
    "BRIGHTNESS": SENSOR_DESCRIPTIONS.get("BRIGHTNESS"),
}


def get_sensor_type_desc_attr(sensor_type, attr, default=None):
    """Get sensor desc attribute from sensor types."""
    sensor_desc = SENSOR_TYPES.get(sensor_type)
    if sensor_desc is not None:
        return getattr(sensor_desc, attr, default)
    return default


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the HomeMatic sensor platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMSensor(conf)
        devices.append(new_device)

    add_entities(devices, True)


class HMSensor(HMDevice, SensorEntity):
    """Representation of a HomeMatic sensor."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        # Does a cast exist for this class?
        name = self._hmdevice.__class__.__name__
        if name in HM_STATE_HA_CAST:
            return HM_STATE_HA_CAST[name].get(self._hm_get_state())

        # No cast, return original value
        return self._hm_get_state()

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return get_sensor_type_desc_attr(self._state, "native_unit_of_measurement")

    @property
    def device_class(self):
        """Return the device class to use in the frontend, if any."""
        return get_sensor_type_desc_attr(self._state, "device_class")

    @property
    def state_class(self) -> str | None:
        """Return the state class of the sensor."""
        return get_sensor_type_desc_attr(self._state, "state_class")

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return get_sensor_type_desc_attr(self._state, "icon")

    def _init_data_struct(self):
        """Generate a data dictionary (self._data) from metadata."""
        if self._state:
            self._data.update({self._state: None})
        else:
            _LOGGER.critical("Unable to initialize sensor: %s", self._name)
