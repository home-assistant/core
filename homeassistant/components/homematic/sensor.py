"""Support for HomeMatic sensors."""
from __future__ import annotations

from copy import copy
import logging

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    ATTR_NAME,
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

from .const import ATTR_DISCOVER_DEVICES, ATTR_PARAM
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
    "HUMIDITY": SensorEntityDescription(
        key="HUMIDITY",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "ACTUAL_TEMPERATURE": SensorEntityDescription(
        key="ACTUAL_TEMPERATURE",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "TEMPERATURE": SensorEntityDescription(
        key="TEMPERATURE",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "LUX": SensorEntityDescription(
        key="LUX",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "CURRENT_ILLUMINATION": SensorEntityDescription(
        key="CURRENT_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "ILLUMINATION": SensorEntityDescription(
        key="ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "AVERAGE_ILLUMINATION": SensorEntityDescription(
        key="AVERAGE_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "LOWEST_ILLUMINATION": SensorEntityDescription(
        key="LOWEST_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "HIGHEST_ILLUMINATION": SensorEntityDescription(
        key="HIGHEST_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "POWER": SensorEntityDescription(
        key="POWER",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "IEC_POWER": SensorEntityDescription(
        key="IEC_POWER",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "CURRENT": SensorEntityDescription(
        key="CURRENT",
        native_unit_of_measurement=ELECTRIC_CURRENT_MILLIAMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "CONCENTRATION": SensorEntityDescription(
        key="CONCENTRATION",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=DEVICE_CLASS_CO2,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "ENERGY_COUNTER": SensorEntityDescription(
        key="ENERGY_COUNTER",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "IEC_ENERGY_COUNTER": SensorEntityDescription(
        key="IEC_ENERGY_COUNTER",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "VOLTAGE": SensorEntityDescription(
        key="VOLTAGE",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "GAS_POWER": SensorEntityDescription(
        key="GAS_POWER",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=DEVICE_CLASS_GAS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "GAS_ENERGY_COUNTER": SensorEntityDescription(
        key="GAS_ENERGY_COUNTER",
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
    "WIND_DIRECTION_RANGE": SensorEntityDescription(
        key="WIND_DIRECTION_RANGE",
        native_unit_of_measurement=DEGREE,
    ),
    "SUNSHINEDURATION": SensorEntityDescription(
        key="SUNSHINEDURATION",
        native_unit_of_measurement="#",
    ),
    "AIR_PRESSURE": SensorEntityDescription(
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
        key="BRIGHTNESS",
        native_unit_of_measurement="#",
        icon="mdi:invert-colors",
    ),
}

DEFAULT_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="",
    entity_registry_enabled_default=True,
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the HomeMatic sensor platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        state = conf.get(ATTR_PARAM)
        entity_desc = SENSOR_DESCRIPTIONS.get(state)
        if entity_desc is None:
            name = conf.get(ATTR_NAME)
            _LOGGER.warning(
                "Sensor (%s) entity description is missing. Sensor state (%s) needs to be maintained",
                name,
                state,
            )
            entity_desc = copy(DEFAULT_SENSOR_DESCRIPTION)

        new_device = HMSensor(conf, entity_desc)
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

    def _init_data_struct(self):
        """Generate a data dictionary (self._data) from metadata."""
        if self._state:
            self._data.update({self._state: None})
        else:
            _LOGGER.critical("Unable to initialize sensor: %s", self._name)
