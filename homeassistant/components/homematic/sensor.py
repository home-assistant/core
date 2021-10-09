"""Support for HomeMatic sensors."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
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

DEVICE_CLASS = "device_class"
STATE_CLASS = "state_class"

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

HM_UNIT_HA_CAST = {
    "HUMIDITY": PERCENTAGE,
    "TEMPERATURE": TEMP_CELSIUS,
    "ACTUAL_TEMPERATURE": TEMP_CELSIUS,
    "BRIGHTNESS": "#",
    "POWER": POWER_WATT,
    "CURRENT": ELECTRIC_CURRENT_MILLIAMPERE,
    "VOLTAGE": ELECTRIC_POTENTIAL_VOLT,
    "ENERGY_COUNTER": ENERGY_WATT_HOUR,
    "GAS_POWER": VOLUME_CUBIC_METERS,
    "GAS_ENERGY_COUNTER": VOLUME_CUBIC_METERS,
    "IEC_POWER": POWER_WATT,
    "IEC_ENERGY_COUNTER": ENERGY_WATT_HOUR,
    "LUX": LIGHT_LUX,
    "ILLUMINATION": LIGHT_LUX,
    "CURRENT_ILLUMINATION": LIGHT_LUX,
    "AVERAGE_ILLUMINATION": LIGHT_LUX,
    "LOWEST_ILLUMINATION": LIGHT_LUX,
    "HIGHEST_ILLUMINATION": LIGHT_LUX,
    "RAIN_COUNTER": LENGTH_MILLIMETERS,
    "WIND_SPEED": SPEED_KILOMETERS_PER_HOUR,
    "WIND_DIRECTION": DEGREE,
    "WIND_DIRECTION_RANGE": DEGREE,
    "SUNSHINEDURATION": "#",
    "AIR_PRESSURE": PRESSURE_HPA,
    "FREQUENCY": FREQUENCY_HERTZ,
    "VALUE": "#",
    "VALVE_STATE": PERCENTAGE,
    "CARRIER_SENSE_LEVEL": PERCENTAGE,
    "DUTY_CYCLE_LEVEL": PERCENTAGE,
    "CONCENTRATION": CONCENTRATION_PARTS_PER_MILLION,
}

HM_DEVICE_CLASS_HA_CAST = {
    "HUMIDITY": {
        DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "TEMPERATURE": {
        DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "ACTUAL_TEMPERATURE": {
        DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "LUX": {
        DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE,
        STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "CURRENT_ILLUMINATION": {
        DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE,
        STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "AVERAGE_ILLUMINATION": {
        DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE,
        STATE_CLASS: STATE_CLASS_TOTAL,
    },
    "LOWEST_ILLUMINATION": {
        DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE,
        STATE_CLASS: STATE_CLASS_TOTAL,
    },
    "HIGHEST_ILLUMINATION": {
        DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE,
        STATE_CLASS: STATE_CLASS_TOTAL,
    },
    "POWER": {
        DEVICE_CLASS: DEVICE_CLASS_POWER,
        STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "CURRENT": {
        DEVICE_CLASS: DEVICE_CLASS_CURRENT,
        STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "CONCENTRATION": {
        DEVICE_CLASS: DEVICE_CLASS_CO2,
        STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "ENERGY_COUNTER": {
        DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
    },
}

HM_ICON_HA_CAST = {"WIND_SPEED": "mdi:weather-windy", "BRIGHTNESS": "mdi:invert-colors"}


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
        return HM_UNIT_HA_CAST.get(self._state)

    @property
    def device_class(self):
        """Return the device class to use in the frontend, if any."""
        ha_cast = HM_DEVICE_CLASS_HA_CAST.get(self._state, {})
        return ha_cast.get(DEVICE_CLASS)

    @property
    def state_class(self) -> str | None:
        """Return the state class of the sensor."""
        ha_cast = HM_DEVICE_CLASS_HA_CAST.get(self._state, {})
        return ha_cast.get(STATE_CLASS)

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return HM_ICON_HA_CAST.get(self._state)

    def _init_data_struct(self):
        """Generate a data dictionary (self._data) from metadata."""
        if self._state:
            self._data.update({self._state: None})
        else:
            _LOGGER.critical("Unable to initialize sensor: %s", self._name)
