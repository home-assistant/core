"""
Sensor for Last.fm account status.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.lastfm/
"""
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_API_KEY
import re

ICON = 'mdi:lastfm'

REQUIREMENTS = ['pylast==1.6.0']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Last.fm platform"""
    import pylast as lastfm
    network = lastfm.LastFMNetwork(api_key = config.get(CONF_API_KEY),
        api_secret = config.get('api_secret'))
    add_devices(
        [LastfmSensor(username,
            network) for username in config.get('users', [])])


class LastfmSensor(Entity):
    """A class for the Last.fm account."""

    # pylint: disable=abstract-method
    def __init__(self, user, lastfm):
        """Initialize the sensor."""
        self._user = lastfm.get_user(user)
        self._name = user
        self._lastfm = lastfm
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def entity_id(self):
        """Return the entity ID."""
        return 'sensor.lastfm_{}'.format(self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    # pylint: disable=no-member
    def update(self):
        if self._user.get_now_playing() is None:
            self._state = "Not Scrobbling"
        else:
            now = self._user.get_now_playing()
            self._state = (str(now.artist) + " - " + now.title)
        self._playcount = self._user.get_playcount()
        last = self._user.get_recent_tracks(limit=2)[0]
        self._lastplayed = (str(last.track.artist) + " - " +
                            last.track.title)
        top = self._user.get_top_tracks(limit=1)
        toptitle = re.search("', '(.+?)',", str(top))
        topartist = re.search("'(.+?)',", str(top))
        self._topplayed = (topartist.group(1) + " - " +
                           toptitle.group(1))

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'Play Count': self._playcount, 'Last Played':
                self._lastplayed, 'Top Played': self._topplayed}

    @property
    def entity_picture(self):
        """Avatar of the user."""
        return self._user.get_image()

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON
