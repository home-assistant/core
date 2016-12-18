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

REQUIREMENTS = ['pyiss==1.0']

_LOGGER = logging.getLogger(__name__)

CONF_ISS_VISIBLE = 'visible'
CONF_ISS_NEXT_RISE = 'next_rise'
CONF_TIME_SECOND = 'mn'

DEFAULT_NAME = 'Iss'
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
    sensors.append(IssSensor(iss_data, name, CONF_ISS_VISIBLE))
    sensors.append(IssSensor(iss_data, name, CONF_ISS_NEXT_RISE))

    add_devices(sensors, True)


class IssSensor(Entity):
    """Implementation of a ISS sensor."""

    def __init__(self, iss_data, name, sensor_type):
        """Initialize the sensor."""
        self.iss_data = iss_data
        self._state = None
        self._client_name = name

        if sensor_type is CONF_ISS_VISIBLE:
            self._name = CONF_ISS_VISIBLE
            self._unit_of_measurement = None
            self._icon = 'mdi:eye'
        elif sensor_type is CONF_ISS_NEXT_RISE:
            self._name = CONF_ISS_NEXT_RISE
            self._unit_of_measurement = CONF_TIME_SECOND
            self._icon = 'mdi:timer'

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

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
        if self._name is CONF_ISS_VISIBLE:
            self._state = self.iss_data.is_above
        elif self._name is CONF_ISS_NEXT_RISE:
            delta = self.iss_data.next_rise - datetime.utcnow()
            self._state = int(delta.total_seconds() / 60)


class IssData(object):
    """Get data from the ISS."""

    def __init__(self, latitude, longitude):
        """Initialize the data object."""
        self.is_above = None
        self.next_rise = None
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
            _LOGGER.error(self.next_rise.tzinfo)
        except requests.exceptions.HTTPError as error:
            _LOGGER.error(error)
            return False
