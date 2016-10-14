"""
Support for the Torque OBD application.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.torque/
"""
import logging
import re

import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_EMAIL, CONF_NAME)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

API_PATH = '/api/torque'

DEFAULT_NAME = 'vehicle'
DEPENDENCIES = ['http']
DOMAIN = 'torque'

ENTITY_NAME_FORMAT = '{0} {1}'

SENSOR_EMAIL_FIELD = 'eml'
SENSOR_NAME_KEY = r'userFullName(\w+)'
SENSOR_UNIT_KEY = r'userUnit(\w+)'
SENSOR_VALUE_KEY = r'k(\w+)'

NAME_KEY = re.compile(SENSOR_NAME_KEY)
UNIT_KEY = re.compile(SENSOR_UNIT_KEY)
VALUE_KEY = re.compile(SENSOR_VALUE_KEY)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def decode(value):
    """Double-decode required."""
    return value.encode('raw_unicode_escape').decode('utf-8')


def convert_pid(value):
    """Convert pid from hex string to integer."""
    return int(value, 16)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Torque platform."""
    vehicle = config.get(CONF_NAME)
    email = config.get(CONF_EMAIL)
    sensors = {}

    hass.wsgi.register_view(TorqueReceiveDataView(
        hass, email, vehicle, sensors, add_devices))
    return True


class TorqueReceiveDataView(HomeAssistantView):
    """Handle data from Torque requests."""

    url = API_PATH
    name = 'api:torque'

    # pylint: disable=too-many-arguments
    def __init__(self, hass, email, vehicle, sensors, add_devices):
        """Initialize a Torque view."""
        super().__init__(hass)
        self.email = email
        self.vehicle = vehicle
        self.sensors = sensors
        self.add_devices = add_devices

    def get(self, request):
        """Handle Torque data request."""
        data = request.args

        if self.email is not None and self.email != data[SENSOR_EMAIL_FIELD]:
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
                if pid in self.sensors:
                    self.sensors[pid].on_update(data[key])

        for pid in names:
            if pid not in self.sensors:
                self.sensors[pid] = TorqueSensor(
                    ENTITY_NAME_FORMAT.format(self.vehicle, names[pid]),
                    units.get(pid, None))
                self.add_devices([self.sensors[pid]])

        return None


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
