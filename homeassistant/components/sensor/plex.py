"""
Support for Plex media server monitoring.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.plex/
"""
from datetime import timedelta
import voluptuous as vol

from homeassistant.const import CONF_PLATFORM, CONF_USERNAME
from homeassistant.const import CONF_PASSWORD, CONF_HOST, CONF_PORT
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = [
    'https://github.com/nkgilley/python-plex-api/archive/'
    '22a3279bce552122afac694e481a3064a8ab9b0f.zip#python-plex-api==0.0.1']

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'plex',
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_HOST, default='localhost'): cv.string,
    vol.Optional(CONF_PORT, default=32400): vol.All(vol.Coerce(int),
                                                    vol.Range(min=1,
                                                              max=65535))
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Demo sensors."""
    plex_user = config.get(CONF_USERNAME)
    plex_password = config.get(CONF_PASSWORD)
    plex_host = config.get(CONF_HOST)
    plex_port = config.get(CONF_PORT)
    add_devices([PlexSensor('Plex', plex_user, plex_password,
                            (plex_host, plex_port))])


class PlexSensor(Entity):
    """Plex now playing sensor."""

    def __init__(self, name, plex_user, plex_password, plex_server):
        """Initialize the sensor."""
        self._name = name
        self._state = 0
        self._now_playing = []
        self._user = plex_user
        self._host = plex_server[0]
        self._port = plex_server[1]

        from pyplex import get_auth_token
        self._auth_token = get_auth_token(plex_user, plex_password)

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
        data = {}
        for content in self._now_playing:
            data[content[0]] = content[1]
        return data

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update method for plex sensor."""
        from pyplex import get_now_playing
        data = get_now_playing(auth_token=self._auth_token,
                               plex_user=self._user,
                               plex_host=self._host,
                               plex_port=self._port)
        now_playing = []
        for index, user in enumerate(data['user_list']):
            if data['user_list'][index]:
                user = data['user_list'][index]
            else:
                user = self._user
            video = data['movie_title'][index]
            year = data['movie_year'][index]
            now_playing.append((user, "{0} ({1})".format(video, year)))
        self._state = len(data['user_list'])
        self._now_playing = now_playing
