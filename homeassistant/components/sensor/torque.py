"""
Support for the Torque OBD application.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.torque/
"""

import re

from homeassistant.const import HTTP_OK
from homeassistant.helpers.entity import Entity

DOMAIN = 'torque'
DEPENDENCIES = ['http']
SENSOR_EMAIL_FIELD = 'eml'
DEFAULT_NAME = 'vehicle'
ENTITY_NAME_FORMAT = '{0} {1}'

API_PATH = '/api/torque'
SENSOR_NAME_KEY = r'userFullName(\w+)'
SENSOR_UNIT_KEY = r'userUnit(\w+)'
SENSOR_VALUE_KEY = r'k(\w+)'

NAME_KEY = re.compile(SENSOR_NAME_KEY)
UNIT_KEY = re.compile(SENSOR_UNIT_KEY)
VALUE_KEY = re.compile(SENSOR_VALUE_KEY)


def decode(value):
    """Double-decode required."""
    return value.encode('raw_unicode_escape').decode('utf-8')


def convert_pid(value):
    """Convert pid from hex string to integer."""
    return int(value, 16)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Torque platform."""
    vehicle = config.get('name', DEFAULT_NAME)
    email = config.get('email', None)
    sensors = {}

    def _receive_data(handler, path_match, data):
        """Received data from Torque."""
        handler.send_response(HTTP_OK)
        handler.end_headers()

        if email is not None and email != data[SENSOR_EMAIL_FIELD]:
            return

        names = {}
        units = {}
        for key in data:
            is_name = NAME_KEY.match(key)
            is_unit = UNIT_KEY.match(key)
            is_value = VALUE_KEY.match(key)

            if is_name:
                pid = convert_pid(is_name.group(1))
                names[pid] = decode(data[key])
            elif is_unit:
                pid = convert_pid(is_unit.group(1))
                units[pid] = decode(data[key])
            elif is_value:
                pid = convert_pid(is_value.group(1))
                if pid in sensors:
                    sensors[pid].on_update(data[key])

        for pid in names:
            if pid not in sensors:
                sensors[pid] = TorqueSensor(
                    ENTITY_NAME_FORMAT.format(vehicle, names[pid]),
                    units.get(pid, None))
                add_devices([sensors[pid]])

    hass.http.register_path('GET', API_PATH, _receive_data)
    return True


class TorqueSensor(Entity):
    """Representation of a Torque sensor."""

    def __init__(self, name, unit):
        """Initialize the sensor."""
        self._name = name
        self._unit = unit
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the default icon of the sensor."""
        return 'mdi:car'

    def on_update(self, value):
        """Receive an update."""
        self._state = value
        self.update_ha_state()
