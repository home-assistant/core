"""
Support for getting statistical data from a Pi-hole system.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.pi_hole/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_MONITORED_CONDITIONS, CONF_NAME, CONF_SSL, CONF_VERIFY_SSL)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['hole==0.3.0']

_LOGGER = logging.getLogger(__name__)

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

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

MONITORED_CONDITIONS = {
    'ads_blocked_today':
        ['Ads Blocked Today', 'ads', 'mdi:close-octagon-outline'],
    'ads_percentage_today':
        ['Ads Percentage Blocked Today', '%', 'mdi:close-octagon-outline'],
    'clients_ever_seen':
        ['Seen Clients', 'clients', 'mdi:account-outline'],
    'dns_queries_today':
        ['DNS Queries Today', 'queries', 'mdi:comment-question-outline'],
    'domains_being_blocked':
        ['Domains Blocked', 'domains', 'mdi:block-helper'],
    'queries_cached':
        ['DNS Queries Cached', 'queries', 'mdi:comment-question-outline'],
    'queries_forwarded':
        ['DNS Queries Forwarded', 'queries', 'mdi:comment-question-outline'],
    'unique_clients':
        ['DNS Unique Clients', 'clients', 'mdi:account-outline'],
    'unique_domains':
        ['DNS Unique Domains', 'domains', 'mdi:domain'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    vol.Optional(CONF_LOCATION, default=DEFAULT_LOCATION): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    vol.Optional(CONF_MONITORED_CONDITIONS,
                 default=['ads_blocked_today']):
    vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]),
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Pi-hole sensor."""
    from hole import Hole

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    use_tls = config.get(CONF_SSL)
    location = config.get(CONF_LOCATION)
    verify_tls = config.get(CONF_VERIFY_SSL)

    session = async_get_clientsession(hass)
    pi_hole = PiHoleData(Hole(
        host, hass.loop, session, location=location, tls=use_tls,
        verify_tls=verify_tls))

    await pi_hole.async_update()

    if pi_hole.api.data is None:
        raise PlatformNotReady

    sensors = [PiHoleSensor(pi_hole, name, condition)
               for condition in config[CONF_MONITORED_CONDITIONS]]

    async_add_entities(sensors, True)


class PiHoleSensor(Entity):
    """Representation of a Pi-hole sensor."""

    def __init__(self, pi_hole, name, condition):
        """Initialize a Pi-hole sensor."""
        self.pi_hole = pi_hole
        self._name = name
        self._condition = condition

        variable_info = MONITORED_CONDITIONS[condition]
        self._condition_name = variable_info[0]
        self._unit_of_measurement = variable_info[1]
        self._icon = variable_info[2]
        self.data = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self._name, self._condition_name)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the device."""
        try:
            return round(self.data[self._condition], 2)
        except TypeError:
            return self.data[self._condition]

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Pi-Hole."""
        return {
            ATTR_BLOCKED_DOMAINS: self.data['domains_being_blocked'],
        }

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.pi_hole.available

    async def async_update(self):
        """Get the latest data from the Pi-hole API."""
        await self.pi_hole.async_update()
        self.data = self.pi_hole.api.data


class PiHoleData:
    """Get the latest data and update the states."""

    def __init__(self, api):
        """Initialize the data object."""
        self.api = api
        self.available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from the Pi-hole."""
        from hole.exceptions import HoleError

        try:
            await self.api.get_data()
            self.available = True
        except HoleError:
            _LOGGER.error("Unable to fetch data from Pi-hole")
            self.available = False
