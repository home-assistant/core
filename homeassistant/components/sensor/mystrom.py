"""
Support for myStrom switches sensor

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.mystrom/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_HOST, CONF_NAME, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

ICON = 'mdi:gauge'

SCAN_INTERVAL = timedelta(seconds=60)

UNIT_OF_MEASUREMENT = 'W'

REQUIREMENTS = ['python-mystrom==0.3.8']

DEFAULT_NAME = 'myStrom Switch'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the myStrom sensor."""
    from pymystrom import MyStromPlug, exceptions

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    try:
        MyStromPlug(host).get_status()
    except exceptions.MyStromConnectionError:
        _LOGGER.error("No route to device '%s'", host)
        return False

    add_devices([MyStromSensor(name, host)])

class MyStromSensor(Entity):
    """Representation of a myStrom switch."""

    def __init__(self, name, resource):
        """Initialize the sensor."""
        from pymystrom import MyStromPlug

        self._name = name
        self._resource = resource
        self._state = STATE_UNKNOWN
        self._plug = MyStromPlug(self._resource)
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return UNIT_OF_MEASUREMENT

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest data from the device and update the data."""
        from pymystrom import exceptions
        try:
            self._state = round(self._plug.get_consumption(), 2)
        except exceptions.MyStromConnectionError:
            self._state = 0
            _LOGGER.error("No route to device '%s'. Is device offline?",
                          self._resource)
