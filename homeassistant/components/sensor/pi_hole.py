"""
Support for getting statistical data from a Pi-Hole system.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.pi_hole/
"""
import logging
import json

import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.sensor.rest import RestData
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_SSL, CONF_VERIFY_SSL)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_ENDPOINT = '/admin/api.php'

ATTR_BLOCKED_DOMAINS = 'domains_blocked'
ATTR_PERCENTAGE_TODAY = 'percentage_today'
ATTR_QUERIES_TODAY = 'queries_today'

DEFAULT_HOST = 'localhost'
DEFAULT_METHOD = 'GET'
DEFAULT_NAME = 'Pi-Hole'
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Pi-Hole sensor."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    method = 'GET'
    payload = None
    auth = None
    headers = None
    verify_ssl = config.get(CONF_VERIFY_SSL)
    use_ssl = config.get(CONF_SSL)

    if use_ssl:
        uri_scheme = 'https://'
    else:
        uri_scheme = 'http://'

    resource = "{}{}{}".format(uri_scheme, host, _ENDPOINT)

    rest = RestData(method, resource, auth, headers, payload, verify_ssl)
    rest.update()

    if rest.data is None:
        _LOGGER.error("Unable to fetch data from Pi-Hole")
        return False

    add_devices([PiHoleSensor(hass, rest, name)])


class PiHoleSensor(Entity):
    """Representation of a Pi-Hole sensor."""

    def __init__(self, hass, rest, name):
        """Initialize a Pi-Hole sensor."""
        self._hass = hass
        self.rest = rest
        self._name = name
        self._state = False
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    # pylint: disable=no-member
    @property
    def state(self):
        """Return the state of the device."""
        return self._state.get('ads_blocked_today')

    # pylint: disable=no-member
    @property
    def state_attributes(self):
        """Return the state attributes of the GPS."""
        return {
            ATTR_BLOCKED_DOMAINS: self._state.get('domains_being_blocked'),
            ATTR_PERCENTAGE_TODAY: self._state.get('ads_percentage_today'),
            ATTR_QUERIES_TODAY: self._state.get('dns_queries_today'),
        }

    def update(self):
        """Get the latest data from REST API and updates the state."""
        try:
            self.rest.update()
            self._state = json.loads(self.rest.data)
        except TypeError:
            _LOGGER.error("Unable to fetch data from Pi-Hole")
