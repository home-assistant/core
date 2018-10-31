"""
A platform which allows you to get information from Tautulli.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/components/sensor.tautulli/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_API_KEY, CONF_HOST,
                                 CONF_MONITORED_CONDITIONS, CONF_NAME,
                                 CONF_PORT, CONF_SSL, CONF_VERIFY_SSL)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pytautulli==0.4.0']

_LOGGER = logging.getLogger(__name__)

CONF_MONITORED_USERS = 'monitored_users'
CONF_UPDATE_INTERVAL = 'update_interval'

DEFAULT_NAME = 'Tautulli'
DEFAULT_PORT = '8181'
DEFAULT_CONDITIONS = 'None'
DEFAULT_USERS = 'None'
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

TIME_BETWEEN_UPDATES = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=DEFAULT_CONDITIONS):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_MONITORED_USERS, default=DEFAULT_USERS):
        vol.All(cv.ensure_list, [cv.string]),
    })


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Create the sensor."""
    from pytautulli import Tautulli

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    api_key = config.get(CONF_API_KEY)
    monitored_conditions = config.get(CONF_MONITORED_CONDITIONS)
    user = config.get(CONF_MONITORED_USERS)
    use_ssl = config.get(CONF_SSL)
    verify_ssl = config.get(CONF_VERIFY_SSL)

    session = async_get_clientsession(hass, verify_ssl)
    tautulli = TautulliData(Tautulli(
        host, port, api_key, hass.loop, session, use_ssl))

    await tautulli.test_connection()

    if not tautulli.test_connection:
        raise PlatformNotReady

    sensor = [TautulliSensor(tautulli, name, monitored_conditions, user)]

    async_add_entities(sensor, True)


class TautulliSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, tautulli, name, monitored_conditions, users):
        """Initialize the sensor."""
        self.tautulli = tautulli
        self.monitored_conditions = monitored_conditions
        self.usernames = users
        self.users = []
        self.sessions = {}
        self.home = {}
        self._attributes = {}
        self._name = name
        self._state = None

    async def async_update(self):
        """Get the latest data from the Tautulli API."""
        await self.tautulli.async_update()
        self.home = self.tautulli.api.home_data
        self.sessions = self.tautulli.api.session_data
        self._attributes['Top Movie'] = self.home[0]['rows'][0]['title']
        self._attributes['Top TV Show'] = self.home[3]['rows'][0]['title']
        self._attributes['Top User'] = self.home[7]['rows'][0]['user']
        for key in self.sessions:
            if 'sessions' not in key:
                self._attributes[key] = self.sessions[key]
        for user in self.tautulli.api.users:
            if user in self.users or not self.users:
                userdata = self.tautulli.api.user_data
                self._attributes[user] = {}
                self._attributes[user]['Activity'] = userdata[user]['Activity']
                for key in self.monitored_conditions:
                    if key != 'None':
                        try:
                            self._attributes[user][key] = userdata[user][key]
                        except (KeyError, TypeError):
                            self._attributes[user][key] = ''

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.sessions['stream_count']

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return 'mdi:plex'

    @property
    def device_state_attributes(self):
        """Return attributes for the sensor."""
        return self._attributes


class TautulliData:
    """Get the latest data and update the states."""

    def __init__(self, api):
        """Initialize the data object."""
        self.api = api

    @Throttle(TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from Tautulli."""
        await self.api.get_data()

    async def test_connection(self):
        """Test connection to Tautulli."""
        connection_status = await self.api.test_connection()
        return connection_status
