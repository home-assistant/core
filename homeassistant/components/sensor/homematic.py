"""
The homematic sensor platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.homematic/

Important: For this platform to work the homematic component has to be
properly configured.
"""

import logging
from homeassistant.const import STATE_UNKNOWN
import homeassistant.components.homematic as homematic

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']

HM_STATE_HA_CAST = {
    "RotaryHandleSensor": {0: "closed", 1: "tilted", 2: "open"},
    "WaterSensor": {0: "dry", 1: "wet", 2: "water"},
    "CO2Sensor": {0: "normal", 1: "added", 2: "strong"},
}

HM_UNIT_HA_CAST = {
    "HUMIDITY": "%",
    "TEMPERATURE": "°C",
    "BRIGHTNESS": "#",
    "POWER": "W",
    "CURRENT": "mA",
    "VOLTAGE": "V",
    "ENERGY_COUNTER": "Wh",
    "GAS_POWER": "m3",
    "GAS_ENERGY_COUNTER": "m3",
    "LUX": "lux",
    "RAIN_COUNTER": "mm",
    "WIND_SPEED": "km/h",
    "WIND_DIRECTION": "°",
    "WIND_DIRECTION_RANGE": "°",
    "SUNSHINEDURATION": "#",
    "AIR_PRESSURE": "hPa",
    "FREQUENCY": "Hz",
}


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the platform."""
    if discovery_info is None:
        return

    return homematic.setup_hmdevice_discovery_helper(
        HMSensor,
        discovery_info,
        add_callback_devices
    )


class HMSensor(homematic.HMDevice):
    """Represents various Homematic sensors in Home Assistant."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.available:
            return STATE_UNKNOWN

        # Does a cast exist for this class?
        name = self._hmdevice.__class__.__name__
        if name in HM_STATE_HA_CAST:
            return HM_STATE_HA_CAST[name].get(self._hm_get_state(), None)

        # No cast, return original value
        return self._hm_get_state()

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if not self.available:
            return None

        return HM_UNIT_HA_CAST.get(self._state, None)

    def _init_data_struct(self):
        """Generate a data dict (self._data) from hm metadata."""
        # Add state to data dict
        if self._state:
            _LOGGER.debug("%s init datadict with main node '%s'", self._name,
                          self._state)
            self._data.update({self._state: STATE_UNKNOWN})
        else:
            _LOGGER.critical("Can't correctly init sensor %s.", self._name)
