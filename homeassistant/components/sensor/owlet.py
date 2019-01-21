"""
Support for Owlet sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.owlet/
"""
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.owlet import DOMAIN
from homeassistant.util import dt as dt_util

DEPENDENCIES = ['owlet']

SCAN_INTERVAL = timedelta(seconds=120)

SENSOR_CONDITIONS = {
    'oxygen_level': {
        'name': 'Oxygen Level',
        'device_class': ''
    },
    'heart_rate': {
        'name': 'Heart Rate',
        'device_class': ''
    }
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup owlet binary sensor."""
    device = hass.data[DOMAIN]

    entities = []
    for condition in SENSOR_CONDITIONS:
        if condition in device.monitor:
            entities.append(OwletSensor(device, condition))

    add_entities(entities, True)


class OwletSensor(BinarySensorDevice):
    """Representation of owlet binary sensor."""

    def __init__(self, device, condition):
        """Init owlet binary sensor."""
        self._device = device
        self._condition = condition
        self._state = None
        self._prop_expiration = None
        self._is_charging = None
        self._battery_level = None
        self._sock_off = None
        self._sock_connection = None
        self._movement = None

    @property
    def name(self):
        """Return sensor name."""
        return '{} {}'.format(self._device.name,
                              SENSOR_CONDITIONS[self._condition]['name'])

    @property
    def state(self):
        """Return current state of sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class."""
        return SENSOR_CONDITIONS[self._condition]['device_class']

    @property
    def is_charging(self):
        """Return device is_charging value"""
        return self._is_charging

    @property
    def battery_level(self):
        """Return device battery_level value"""
        return self._battery_level

    @property
    def sock_off(self):
        """Return device sock_off value"""
        return self._sock_off

    @property
    def sock_connection(self):
        """Return device sock_connection value"""
        return self._sock_connection

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        attributes = {
            'battery_charging': self.is_charging,
            'battery_level': self.battery_level,
            'sock_off': self.sock_off,
            'sock_connection': self.sock_connection
        }

        return attributes

    def update(self):
        """Update state of sensor."""

        self._is_charging = self._device.device.charge_status
        self._battery_level = self._device.device.batt_level
        self._sock_off = self._device.device.sock_off
        self._sock_connection = self._device.device.sock_connection
        self._movement = self._device.device.movement
        self._prop_expiration = self._device.device.prop_expire_time

        value = getattr(self._device.device, self._condition)

        if self._condition == 'batt_level':
            self._state = 100 if value > 100 else value
            return

        if not self._device.device.base_station_on:
            value = '-'

        elif self._device.device.charge_status > 0:
            value = '-'

        # handle expired values
        elif self._prop_expiration < dt_util.now().timestamp():
            value = '-'

        elif self._movement:
            value = '-'

        self._state = value
