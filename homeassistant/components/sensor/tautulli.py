"""
A platform which allows you to get information from Tautulli.

For more details about this component, please refer to the documentation at
https://www.home-assistant.io/components/sensor.tautulli
"""

import logging
import voluptuous as vol
from homeassistant.helpers.entity import Entity
from homeassistant.const import (CONF_API_KEY,
                                 CONF_HOST,
                                 CONF_MONITORED_VARIABLES,
                                 CONF_PORT,
                                 CONF_SSL,
                                 STATE_UNAVAILABLE)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import (PLATFORM_SCHEMA)

__version__ = '1.1.0'

REQUIREMENTS = ['pytautulli==0.1.4']

_LOGGER = logging.getLogger(__name__)

CONF_MONITORED_USERS = 'monitored_users'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default='8181'): cv.string,
    vol.Optional(CONF_SSL, default=False): cv.boolean,
    vol.Optional(CONF_MONITORED_VARIABLES, default=None):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_MONITORED_USERS, default=None):
        vol.All(cv.ensure_list, [cv.string]),
    })


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Create the sensor."""
    api_key = config.get(CONF_API_KEY)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    monitored_variables = config.get(CONF_MONITORED_VARIABLES)
    monitored_users = config.get(CONF_MONITORED_USERS)
    ssl = config.get(CONF_SSL)
    if ssl:
        schema = 'https'
    else:
        schema = 'http'
    add_devices([Tautulli(api_key, monitored_variables,
                          host, port, monitored_users, schema)])


class Tautulli(Entity):
    """Representation of a Sensor."""

    def __init__(self, api_key, monitored_variables,
                 host, port, users, schema):
        """Initialize the sensor."""
        import pytautulli
        self.tautulli = pytautulli
        self._state = STATE_UNAVAILABLE
        self._api_key = api_key
        self._monitored_variables = monitored_variables
        self._host = host
        self._port = port
        self._user = users
        self._schema = schema
        self._data = {}
        self.update()

    def update(self):
        """Update sensor value."""
        most_stats = self.tautulli.get_most_stats(self._host,
                                                  self._port,
                                                  self._api_key,
                                                  self._schema)
        for key in most_stats:
            self._data[str(key)] = str(most_stats[key])

        sever_stats = self.tautulli.get_server_stats(self._host,
                                                     self._port,
                                                     self._api_key,
                                                     self._schema)
        for key in sever_stats:
            self._data[str(key)] = str(sever_stats[key])

        users = self.tautulli.get_users(self._host,
                                        self._port,
                                        self._api_key,
                                        self._schema)
        for user in users:
            if user != 'Local' and (user in self._user or self._user is None):
                userstate = self.tautulli.get_user_state(self._host,
                                                         self._port,
                                                         self._api_key,
                                                         user,
                                                         self._schema)
                self._data[str(user)] = {}
                self._data[str(user)]['activity'] = str(userstate)
                attrlist = self.tautulli.get_user_activity(self._host,
                                                           self._port,
                                                           self._api_key,
                                                           user,
                                                           self._schema)
                for key in self._monitored_variables:
                    try:
                        self._data[str(user)][str(key)] = str(attrlist[key])
                    except KeyError:
                        self._data[str(user)][str(key)] = ""
        self._state = sever_stats['count']

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Tautulli'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return 'mdi:plex'

    @property
    def device_state_attributes(self):
        """Return attributes for the sensor."""
        return self._data

