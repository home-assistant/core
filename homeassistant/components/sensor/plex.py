"""
Support for Plex media server monitoring.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.plex/
"""
from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.const import (CONF_NAME, CONF_PLATFORM, CONF_USERNAME,
                                 CONF_PASSWORD, CONF_HOST, CONF_PORT)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['plexapi==1.1.0']

CONF_SERVER = 'server'
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'plex',
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SERVER): cv.string,
    vol.Optional(CONF_NAME, default='Plex'): cv.string,
    vol.Optional(CONF_HOST, default='localhost'): cv.string,
    vol.Optional(CONF_PORT, default=32400): vol.All(vol.Coerce(int),
                                                    vol.Range(min=1,
                                                              max=65535))
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Demo sensors."""
    name = config.get(CONF_NAME)
    plex_user = config.get(CONF_USERNAME)
    plex_password = config.get(CONF_PASSWORD)
    plex_server = config.get(CONF_SERVER)
    plex_host = config.get(CONF_HOST)
    plex_port = config.get(CONF_PORT)
    plex_url = 'http://' + plex_host + ':' + str(plex_port)
    add_devices([PlexSensor(name, plex_url, plex_user,
                            plex_password, plex_server)])


class PlexSensor(Entity):
    """Plex now playing sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, name, plex_url, plex_user, plex_password, plex_server):
        """Initialize the sensor."""
        self._name = name
        self._state = 0
        self._now_playing = []

        if plex_user and plex_password:
            from plexapi.myplex import MyPlexUser
            user = MyPlexUser.signin(plex_user, plex_password)
            server = plex_server if plex_server else user.resources()[0].name
            self._server = user.getResource(server).connect()
        else:
            from plexapi.server import PlexServer
            self._server = PlexServer(plex_url)

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "Watching"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {content[0]: content[1] for content in self._now_playing}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update method for plex sensor."""
        sessions = self._server.sessions()
        now_playing = [(s.user.title, "{0} ({1})".format(s.title, s.year))
                       for s in sessions]
        self._state = len(sessions)
        self._now_playing = now_playing
