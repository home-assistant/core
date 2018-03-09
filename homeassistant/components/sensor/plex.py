"""
Support for Plex media server monitoring.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.plex/
"""
from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_PORT, CONF_TOKEN,
    CONF_SSL)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['plexapi==3.0.6']

_LOGGER = logging.getLogger(__name__)

CONF_SERVER = 'server'

DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'Plex'
DEFAULT_PORT = 32400
DEFAULT_SSL = False

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_TOKEN): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_SERVER): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Plex sensor."""
    name = config.get(CONF_NAME)
    plex_user = config.get(CONF_USERNAME)
    plex_password = config.get(CONF_PASSWORD)
    plex_server = config.get(CONF_SERVER)
    plex_host = config.get(CONF_HOST)
    plex_port = config.get(CONF_PORT)
    plex_token = config.get(CONF_TOKEN)

    plex_url = '{}://{}:{}'.format('https' if config.get(CONF_SSL) else 'http',
                                   plex_host, plex_port)

    import plexapi.exceptions

    try:
        add_devices([PlexSensor(
            name, plex_url, plex_user, plex_password, plex_server,
            plex_token)], True)
    except (plexapi.exceptions.BadRequest, plexapi.exceptions.Unauthorized,
            plexapi.exceptions.NotFound) as error:
        _LOGGER.error(error)
        return


class PlexSensor(Entity):
    """Representation of a Plex now playing sensor."""

    def __init__(self, name, plex_url, plex_user, plex_password,
                 plex_server, plex_token):
        """Initialize the sensor."""
        from plexapi.myplex import MyPlexAccount
        from plexapi.server import PlexServer

        self._name = name
        self._state = 0
        self._now_playing = []

        if plex_token:
            self._server = PlexServer(plex_url, plex_token)
        elif plex_user and plex_password:
            user = MyPlexAccount(plex_user, plex_password)
            server = plex_server if plex_server else user.resources()[0].name
            self._server = user.resource(server).connect()
        else:
            self._server = PlexServer(plex_url)

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
        """Update method for Plex sensor."""
        sessions = self._server.sessions()
        now_playing = []
        for sess in sessions:
            user = sess.usernames[0] if sess.usernames is not None else ""
            title = sess.title if sess.title is not None else ""
            year = sess.year if sess.year is not None else ""
            now_playing.append((user, "{0} ({1})".format(title, year)))
        self._state = len(sessions)
        self._now_playing = now_playing
