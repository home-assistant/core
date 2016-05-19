import requests
import voluptuous as vol
import xml.etree.cElementTree as ET

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_PORT
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

DOMAIN = 'plex'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT): vol.All(vol.Coerce(int),
                                         vol.Range(min=1, max=65535))
    })
}, extra=vol.ALLOW_EXTRA)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Demo sensors."""
    plex_user = config.get(CONF_USERNAME)
    plex_password = config.get(CONF_PASSWORD)
    plex_host = config.get(CONF_HOST) or "localhost"
    plex_port = config.get(CONF_PORT) or 32400
    plex_url = 'http://' + plex_host + ':' + str(plex_port) + '/status/sessions'
    add_devices([PlexSensor('Plex', plex_user, plex_password, plex_url)])

class PlexSensor(Entity):
    """Plex now playing sensor."""

    def __init__(self, name, plex_user, plex_password, plex_url):
        """Initialize the sensor."""
        self._name = name
        self._state = None
        self._user = plex_user
        self._auth_token = self.getAuthToken(plex_user, plex_password)
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

    def getAuthToken(self, plex_user, plex_password):
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
            if 'authentication-token' == auth_elem.tag:
                return auth_elem.text.strip()


    def update(self):
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
        if len(user_list) > 0:
            for index in range(len(user_list)):
                user = user_list[index] if user_list[index] else self._user
                self._state = "{0} is watching {1} ({2})\tState: {3}\n".format(user, movie_title[index], movie_year[index], user_state[index])
        else:
            self._state = 'Nobody is Watching Anything!'