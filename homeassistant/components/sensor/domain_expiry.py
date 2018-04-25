"""
Counter for the days till domain will expire.

For more details about this sensor please refer to the documentation at
https://home-assistant.io/components/sensor.domain_expiry/
"""
import logging
from datetime import datetime, timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_DOMAIN)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['python-whois==0.6.9']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Domain Expiry'

SCAN_INTERVAL = timedelta(hours=24)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DOMAIN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up domain expiry sensor."""
    server_name = config.get(CONF_DOMAIN)
    sensor_name = config.get(CONF_NAME)

    add_devices([DomainExpiry(sensor_name, server_name)], True)


class DomainExpiry(Entity):
    """Implementation of the domain expiry sensor."""

    def __init__(self, sensor_name, server_name):
        """Initialize the sensor."""
        self.server_name = server_name
        self._name = sensor_name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return 'days'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:earth'

    def update(self):
        """Fetch the domain information."""
        import whois
        domain = whois.whois(self.server_name)
        if isinstance(domain.expiration_date, datetime):
            expiry = domain.expiration_date - datetime.today()
            self._state = expiry.days
        else:
            _LOGGER.error("Cannot get expiry date for %s", self.server_name)
