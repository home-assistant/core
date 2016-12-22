"""
Support for International Space Station data sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.iss/
"""
import logging
from datetime import timedelta, datetime
import requests
import voluptuous as vol
from homeassistant.util import Throttle
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyiss==1.0.1']

_LOGGER = logging.getLogger(__name__)

ATTR_ISS_VISIBLE = 'visible'
ATTR_ISS_NEXT_RISE = 'next_rise'
ATTR_ISS_NUMBER_PEOPLE_SPACE = 'number_of_people_in_space'

DEFAULT_NAME = 'ISS'
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ISS sensor."""
    # Validate the configuration
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    try:
        iss_data = IssData(hass.config.latitude, hass.config.longitude)
        iss_data.update()
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(error)
        return False

    name = config.get(CONF_NAME)

    sensors = []
    sensors.append(IssSensor(iss_data, name))

    add_devices(sensors, True)


class IssSensor(Entity):
    """Implementation of a ISS sensor."""

    def __init__(self, iss_data, name):
        """Initialize the sensor."""
        self.iss_data = iss_data
        self._state = None
        self._attributes = {}
        self._client_name = name
        self._name = ATTR_ISS_VISIBLE
        self._unit_of_measurement = None
        self._icon = 'mdi:eye'

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    def update(self):
        """Get the latest data from ISS API and updates the states."""
        self._state = self.iss_data.is_above

        self._attributes[ATTR_ISS_NUMBER_PEOPLE_SPACE] = \
            self.iss_data.number_of_people_in_space
        delta = self.iss_data.next_rise - datetime.utcnow()
        self._attributes[ATTR_ISS_NEXT_RISE] = int(delta.total_seconds() / 60)


class IssData(object):
    """Get data from the ISS."""

    def __init__(self, latitude, longitude):
        """Initialize the data object."""
        self.is_above = None
        self.next_rise = None
        self.number_of_people_in_space = None
        self.latitude = latitude
        self.longitude = longitude

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the ISS."""
        import pyiss

        try:
            iss = pyiss.ISS()
            self.is_above = iss.is_ISS_above(self.latitude, self.longitude)
            self.next_rise = iss.next_rise(self.latitude, self.longitude)
            self.number_of_people_in_space = iss.number_of_people_in_space()
            _LOGGER.error(self.next_rise.tzinfo)
        except requests.exceptions.HTTPError as error:
            _LOGGER.error(error)
            return False
