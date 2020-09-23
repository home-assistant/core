"""Support for HomeMatic sensors."""
import logging

from homeassistant.const import (
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_WATT_HOUR,
    FREQUENCY_HERTZ,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    VOLT,
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
}

HM_UNIT_HA_CAST = {
    "HUMIDITY": PERCENTAGE,
    "TEMPERATURE": TEMP_CELSIUS,
    "ACTUAL_TEMPERATURE": TEMP_CELSIUS,
    "BRIGHTNESS": "#",
    "POWER": POWER_WATT,
    "CURRENT": "mA",
    "VOLTAGE": VOLT,
    "ENERGY_COUNTER": ENERGY_WATT_HOUR,
    "GAS_POWER": VOLUME_CUBIC_METERS,
    "GAS_ENERGY_COUNTER": VOLUME_CUBIC_METERS,
    "LUX": "lx",
    "ILLUMINATION": "lx",
    "CURRENT_ILLUMINATION": "lx",
    "AVERAGE_ILLUMINATION": "lx",
    "LOWEST_ILLUMINATION": "lx",
    "HIGHEST_ILLUMINATION": "lx",
    "RAIN_COUNTER": LENGTH_MILLIMETERS,
    "WIND_SPEED": SPEED_KILOMETERS_PER_HOUR,
    "WIND_DIRECTION": DEGREE,
    "WIND_DIRECTION_RANGE": DEGREE,
    "SUNSHINEDURATION": "#",
    "AIR_PRESSURE": PRESSURE_HPA,
    "FREQUENCY": FREQUENCY_HERTZ,
    "VALUE": "#",
    "VALVE_STATE": PERCENTAGE,
}

HM_DEVICE_CLASS_HA_CAST = {
    "HUMIDITY": DEVICE_CLASS_HUMIDITY,
    "TEMPERATURE": DEVICE_CLASS_TEMPERATURE,
    "ACTUAL_TEMPERATURE": DEVICE_CLASS_TEMPERATURE,
    "LUX": DEVICE_CLASS_ILLUMINANCE,
    "CURRENT_ILLUMINATION": DEVICE_CLASS_ILLUMINANCE,
    "AVERAGE_ILLUMINATION": DEVICE_CLASS_ILLUMINANCE,
    "LOWEST_ILLUMINATION": DEVICE_CLASS_ILLUMINANCE,
    "HIGHEST_ILLUMINATION": DEVICE_CLASS_ILLUMINANCE,
    "POWER": DEVICE_CLASS_POWER,
    "CURRENT": DEVICE_CLASS_POWER,
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


class HMSensor(HMDevice):
    """Representation of a HomeMatic sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        # Does a cast exist for this class?
        name = self._hmdevice.__class__.__name__
        if name in HM_STATE_HA_CAST:
            return HM_STATE_HA_CAST[name].get(self._hm_get_state())

        # No cast, return original value
        return self._hm_get_state()

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return HM_UNIT_HA_CAST.get(self._state)

    @property
    def device_class(self):
        """Return the device class to use in the frontend, if any."""
        return HM_DEVICE_CLASS_HA_CAST.get(self._state)

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
