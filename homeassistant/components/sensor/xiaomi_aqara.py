"""Support for Xiaomi aqara sensors."""
import logging

from homeassistant.components.xiaomi_aqara import (PY_XIAOMI_GATEWAY,
                                                   XiaomiDevice)
from homeassistant.const import TEMP_CELSIUS

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'temperature': [TEMP_CELSIUS, 'mdi:thermometer'],
    'humidity': ['%', 'mdi:water-percent'],
    'illumination': ['lm', 'mdi:weather-sunset'],
    'lux': ['lx', 'mdi:weather-sunset'],
    'pressure': ['hPa', 'mdi:gauge']
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform the setup for Xiaomi devices."""
    devices = []
    for (_, gateway) in hass.data[PY_XIAOMI_GATEWAY].gateways.items():
        for device in gateway.devices['sensor']:
            if device['model'] == 'sensor_ht':
                devices.append(XiaomiSensor(device, 'Temperature',
                                            'temperature', gateway))
                devices.append(XiaomiSensor(device, 'Humidity',
                                            'humidity', gateway))
            elif device['model'] == 'weather.v1':
                devices.append(XiaomiSensor(device, 'Temperature',
                                            'temperature', gateway))
                devices.append(XiaomiSensor(device, 'Humidity',
                                            'humidity', gateway))
                devices.append(XiaomiSensor(device, 'Pressure',
                                            'pressure', gateway))
            elif device['model'] == 'sensor_motion.aq2':
                devices.append(XiaomiSensor(device, 'Illumination',
                                            'lux', gateway))
            elif device['model'] == 'gateway':
                devices.append(XiaomiSensor(device, 'Illumination',
                                            'illumination', gateway))
    add_devices(devices)


class XiaomiSensor(XiaomiDevice):
    """Representation of a XiaomiSensor."""

    def __init__(self, device, name, data_key, xiaomi_hub):
        """Initialize the XiaomiSensor."""
        self._data_key = data_key
        XiaomiDevice.__init__(self, device, name, xiaomi_hub)

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        try:
            return SENSOR_TYPES.get(self._data_key)[1]
        except TypeError:
            return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        try:
            return SENSOR_TYPES.get(self._data_key)[0]
        except TypeError:
            return None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        value = data.get(self._data_key)
        if value is None:
            return False
        value = float(value)
        if self._data_key in ['temperature', 'humidity', 'pressure']:
            value /= 100
        elif self._data_key in ['illumination']:
            value = max(value - 300, 0)
        if self._data_key == 'temperature' and (value < -50 or value > 60):
            return False
        elif self._data_key == 'humidity' and (value <= 0 or value > 100):
            return False
        elif self._data_key == 'pressure' and value == 0:
            return False
        self._state = round(value, 1)
        return True
