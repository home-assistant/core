"""
The HomeMatic sensor platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.homematic/
"""
import logging
from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.homematic import HMDevice, ATTR_DISCOVER_DEVICES

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']

HM_STATE_HA_CAST = {
    'RotaryHandleSensor': {0: 'closed', 1: 'tilted', 2: 'open'},
    'WaterSensor': {0: 'dry', 1: 'wet', 2: 'water'},
    'CO2Sensor': {0: 'normal', 1: 'added', 2: 'strong'},
}

HM_UNIT_HA_CAST = {
    'HUMIDITY': '%',
    'TEMPERATURE': '°C',
    'BRIGHTNESS': '#',
    'POWER': 'W',
    'CURRENT': 'mA',
    'VOLTAGE': 'V',
    'ENERGY_COUNTER': 'Wh',
    'GAS_POWER': 'm3',
    'GAS_ENERGY_COUNTER': 'm3',
    'LUX': 'lux',
    'RAIN_COUNTER': 'mm',
    'WIND_SPEED': 'km/h',
    'WIND_DIRECTION': '°',
    'WIND_DIRECTION_RANGE': '°',
    'SUNSHINEDURATION': '#',
    'AIR_PRESSURE': 'hPa',
    'FREQUENCY': 'Hz',
    'VALUE': '#',
}

HM_ICON_HA_CAST = {
    'WIND_SPEED': 'mdi:weather-windy',
    'HUMIDITY': 'mdi:water-percent',
    'TEMPERATURE': 'mdi:thermometer',
    'LUX': 'mdi:weather-sunny',
    'BRIGHTNESS': 'mdi:invert-colors',
    'POWER': 'mdi:flash-red-eye',
    'CURRENT': 'mdi:flash-red-eye',
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the HomeMatic platform."""
    if discovery_info is None:
        return

    devices = []
    for config in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMSensor(hass, config)
        new_device.link_homematic()
        devices.append(new_device)

    add_devices(devices)


class HMSensor(HMDevice):
    """Represents various HomeMatic sensors in Home Assistant."""

    @property
    def state(self):
        """Return the state of the sensor."""
        # Does a cast exist for this class?
        name = self._hmdevice.__class__.__name__
        if name in HM_STATE_HA_CAST:
            return HM_STATE_HA_CAST[name].get(self._hm_get_state(), None)

        # No cast, return original value
        return self._hm_get_state()

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return HM_UNIT_HA_CAST.get(self._state, None)

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return HM_ICON_HA_CAST.get(self._state, None)

    def _init_data_struct(self):
        """Generate a data dictionary (self._data) from metadata."""
        if self._state:
            self._data.update({self._state: STATE_UNKNOWN})
        else:
            _LOGGER.critical("Can't initialize sensor %s", self._name)
