"""
Support for International Space Station data sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.iss/
"""
import logging
from datetime import timedelta, datetime

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, ATTR_LONGITUDE, ATTR_LATITUDE, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyiss==1.0.1']

_LOGGER = logging.getLogger(__name__)

ATTR_ISS_VISIBLE = 'visible'
ATTR_ISS_NEXT_RISE = 'next_rise'
ATTR_ISS_NUMBER_PEOPLE_SPACE = 'number_of_people_in_space'

CONF_SHOW_ON_MAP = 'show_on_map'

DEFAULT_NAME = 'ISS'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ISS sensor."""
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
    show_on_map = config.get(CONF_SHOW_ON_MAP)

    add_devices([IssSensor(iss_data, name, show_on_map)], True)


class IssSensor(Entity):
    """Implementation of the ISS sensor."""

    def __init__(self, iss_data, name, show):
        """Initialize the sensor."""
        self.iss_data = iss_data
        self._state = None
        self._attributes = {}
        self._client_name = name
        self._name = ATTR_ISS_VISIBLE
        self._show_on_map = show
        self._unit_of_measurement = None
        self._icon = 'mdi:rocket'
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.iss_data:
            return self.iss_data.is_above
        else:
            return STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.iss_data:
            delta = self.iss_data.next_rise - datetime.utcnow()
            attrs = {
                ATTR_ISS_NUMBER_PEOPLE_SPACE:
                    self.iss_data.number_of_people_in_space,
                ATTR_ISS_NEXT_RISE: int(delta.total_seconds() / 60),
            }
            if self._show_on_map:
                attrs[ATTR_LONGITUDE] = self.iss_data.position.get('longitude')
                attrs[ATTR_LATITUDE] = self.iss_data.position.get('latitude')
            else:
                attrs['long'] = self.iss_data.position.get('longitude')
                attrs['lat'] = self.iss_data.position.get('latitude')
            return attrs

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
        self.iss_data.update()


class IssData(object):
    """Get data from the ISS API."""

    def __init__(self, latitude, longitude):
        """Initialize the data object."""
        self.is_above = None
        self.next_rise = None
        self.number_of_people_in_space = None
        self.position = None
        self.latitude = latitude
        self.longitude = longitude

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the ISS API."""
        import pyiss

        try:
            iss = pyiss.ISS()
            self.is_above = iss.is_ISS_above(self.latitude, self.longitude)
            self.next_rise = iss.next_rise(self.latitude, self.longitude)
            self.number_of_people_in_space = iss.number_of_people_in_space()
            self.position = iss.current_location()
        except requests.exceptions.HTTPError as error:
            _LOGGER.error(error)
            return False
