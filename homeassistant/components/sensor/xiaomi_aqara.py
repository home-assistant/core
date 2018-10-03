"""Support for Xiaomi aqara sensors."""
import logging

from homeassistant.components.xiaomi_aqara import (PY_XIAOMI_GATEWAY,
                                                   XiaomiDevice)
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS, DEVICE_CLASS_PRESSURE)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'temperature': [TEMP_CELSIUS, None, DEVICE_CLASS_TEMPERATURE],
    'humidity': ['%', None, DEVICE_CLASS_HUMIDITY],
    'illumination': ['lm', None, DEVICE_CLASS_ILLUMINANCE],
    'lux': ['lx', None, DEVICE_CLASS_ILLUMINANCE],
    'pressure': ['hPa', None, DEVICE_CLASS_PRESSURE]
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Xiaomi devices."""
    devices = []
    for (_, gateway) in hass.data[PY_XIAOMI_GATEWAY].gateways.items():
        for device in gateway.devices['sensor']:
            if device['model'] == 'sensor_ht':
                devices.append(XiaomiSensor(device, 'Temperature',
                                            'temperature', gateway))
                devices.append(XiaomiSensor(device, 'Humidity',
                                            'humidity', gateway))
            elif device['model'] in ['weather', 'weather.v1']:
                devices.append(XiaomiSensor(device, 'Temperature',
                                            'temperature', gateway))
                devices.append(XiaomiSensor(device, 'Humidity',
                                            'humidity', gateway))
                devices.append(XiaomiSensor(device, 'Pressure',
                                            'pressure', gateway))
            elif device['model'] == 'sensor_motion.aq2':
                devices.append(XiaomiSensor(device, 'Illumination',
                                            'lux', gateway))
            elif device['model'] in ['gateway', 'gateway.v3', 'acpartner.v3']:
                devices.append(XiaomiSensor(device, 'Illumination',
                                            'illumination', gateway))
    add_entities(devices)


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
    def device_class(self):
        """Return the device class of this entity."""
        return SENSOR_TYPES.get(self._data_key)[2] \
            if self._data_key in SENSOR_TYPES else None

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
        if self._data_key == 'humidity' and (value <= 0 or value > 100):
            return False
        if self._data_key == 'pressure' and value == 0:
            return False
        self._state = round(value, 1)
        return True
