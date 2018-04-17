"""
Support for getting statistical data from a Pi-Hole system.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.pi_hole/
"""
import logging
import json
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_SSL, CONF_VERIFY_SSL, CONF_MONITORED_CONDITIONS)

_LOGGER = logging.getLogger(__name__)
_ENDPOINT = '/api.php'

ATTR_BLOCKED_DOMAINS = 'domains_blocked'
ATTR_PERCENTAGE_TODAY = 'percentage_today'
ATTR_QUERIES_TODAY = 'queries_today'

CONF_LOCATION = 'location'
DEFAULT_HOST = 'localhost'

DEFAULT_LOCATION = 'admin'
DEFAULT_METHOD = 'GET'
DEFAULT_NAME = 'Pi-Hole'
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

SCAN_INTERVAL = timedelta(minutes=5)

MONITORED_CONDITIONS = {
    'dns_queries_today': ['DNS Queries Today',
                          'queries', 'mdi:comment-question-outline'],
    'ads_blocked_today': ['Ads Blocked Today',
                          'ads', 'mdi:close-octagon-outline'],
    'ads_percentage_today': ['Ads Percentage Blocked Today',
                             '%', 'mdi:close-octagon-outline'],
    'domains_being_blocked': ['Domains Blocked',
                              'domains', 'mdi:block-helper'],
    'queries_cached': ['DNS Queries Cached',
                       'queries', 'mdi:comment-question-outline'],
    'queries_forwarded': ['DNS Queries Forwarded',
                          'queries', 'mdi:comment-question-outline'],
    'unique_clients': ['DNS Unique Clients',
                       'clients', 'mdi:account-outline'],
    'unique_domains': ['DNS Unique Domains',
                       'domains', 'mdi:domain'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    vol.Optional(CONF_LOCATION, default=DEFAULT_LOCATION): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    vol.Optional(CONF_MONITORED_CONDITIONS,
                 default=list(MONITORED_CONDITIONS)):
    vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Pi-Hole sensor."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    use_ssl = config.get(CONF_SSL)
    location = config.get(CONF_LOCATION)
    verify_ssl = config.get(CONF_VERIFY_SSL)

    api = PiHoleAPI('{}/{}'.format(host, location), use_ssl, verify_ssl)

    sensors = [PiHoleSensor(hass, api, name, condition)
               for condition in config[CONF_MONITORED_CONDITIONS]]

    add_devices(sensors, True)


class PiHoleSensor(Entity):
    """Representation of a Pi-Hole sensor."""

    def __init__(self, hass, api, name, variable):
        """Initialize a Pi-Hole sensor."""
        self._hass = hass
        self._api = api
        self._name = name
        self._var_id = variable

        variable_info = MONITORED_CONDITIONS[variable]
        self._var_name = variable_info[0]
        self._var_units = variable_info[1]
        self._var_icon = variable_info[2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self._name, self._var_name)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._var_icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._var_units

    # pylint: disable=no-member
    @property
    def state(self):
        """Return the state of the device."""
        try:
            return round(self._api.data[self._var_id], 2)
        except TypeError:
            return self._api.data[self._var_id]

    # pylint: disable=no-member
    @property
    def device_state_attributes(self):
        """Return the state attributes of the Pi-Hole."""
        return {
            ATTR_BLOCKED_DOMAINS: self._api.data['domains_being_blocked'],
        }

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._api.available

    def update(self):
        """Get the latest data from the Pi-Hole API."""
        self._api.update()


class PiHoleAPI(object):
    """Get the latest data and update the states."""

    def __init__(self, host, use_ssl, verify_ssl):
        """Initialize the data object."""
        from homeassistant.components.sensor.rest import RestData

        uri_scheme = 'https://' if use_ssl else 'http://'
        resource = "{}{}{}".format(uri_scheme, host, _ENDPOINT)

        self._rest = RestData('GET', resource, None, None, None, verify_ssl)
        self.data = None
        self.available = True
        self.update()

    def update(self):
        """Get the latest data from the Pi-Hole."""
        try:
            self._rest.update()
            self.data = json.loads(self._rest.data)
            self.available = True
        except TypeError:
            _LOGGER.error("Unable to fetch data from Pi-Hole")
            self.available = False
