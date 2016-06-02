"""
Support for Plex media server monitoring.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.plex/
"""
from datetime import timedelta
import xml.etree.cElementTree as ET
import requests
import voluptuous as vol

from homeassistant.const import CONF_PLATFORM, CONF_USERNAME
from homeassistant.const import CONF_PASSWORD, CONF_HOST, CONF_PORT
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'plex',
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_HOST, default='localhost'): cv.string,
    vol.Optional(CONF_PORT, default=32400): vol.All(vol.Coerce(int),
                                                    vol.Range(min=1,
                                                              max=65535))
})


def get_auth_token(plex_user, plex_password):
    """Get Plex authorization token."""
    auth_url = 'https://my.plexapp.com/users/sign_in.xml'
    auth_params = {'user[login]': plex_user,
                   'user[password]': plex_password}

    headers = {
        'X-Plex-Product': 'Plex API',
        'X-Plex-Version': "2.0",
        'X-Plex-Client-Identifier': '012286'
    }

    response = requests.post(auth_url, data=auth_params, headers=headers)
    auth_tree = ET.fromstring(response.text)
    for auth_elem in auth_tree.getiterator():
        if auth_elem.tag == 'authentication-token':
            return auth_elem.text.strip()


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Demo sensors."""
    plex_user = config.get(CONF_USERNAME)
    plex_password = config.get(CONF_PASSWORD)
    plex_host = config.get(CONF_HOST)
    plex_port = config.get(CONF_PORT)
    url = 'http://' + plex_host + ':' + str(plex_port) + '/status/sessions'
    add_devices([PlexSensor('Plex', plex_user, plex_password, url)])


class PlexSensor(Entity):
    """Plex now playing sensor."""

    def __init__(self, name, plex_user, plex_password, plex_url):
        """Initialize the sensor."""
        self._name = name
        self._now_playing = []
        self._user = plex_user
        self._auth_token = get_auth_token(plex_user, plex_password)
        self._url = plex_url
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
        for idx, content in enumerate(self._now_playing):
            data[str(idx + 1)] = content
        return data

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update method for plex sensor."""
        plex_response = requests.post(self._url +
                                      '?X-Plex-Token=' + self._auth_token)
        tree = ET.fromstring(plex_response.text)

        movie_title = []
        movie_year = []
        user_list = []
        user_state = []

        for elem in tree.getiterator('MediaContainer'):
            for video_elem in elem.iter('Video'):
                if video_elem.attrib['type'] == 'episode':
                    movie_title.append(video_elem.attrib['grandparentTitle'] +
                                       ' - ' + video_elem.attrib['title'])
                else:
                    movie_title.append(video_elem.attrib['title'])
                movie_year.append(video_elem.attrib['year'])
                for user_elem in video_elem.iter('User'):
                    user_list.append(user_elem.attrib['title'])
                for state_elem in video_elem.iter('Player'):
                    user_state.append(state_elem.attrib['state'])
        self._now_playing = []
        for index, user in enumerate(user_list):
            user = user_list[index] if user_list[index] else self._user
            video = movie_title[index]
            year = movie_year[index]
            self._now_playing.append("{0} is watching {1} ({2})".format(user,
                                                                        video,
                                                                        year))
        self._state = len(user_list)
