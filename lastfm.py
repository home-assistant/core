"""
Sensor for Last.fm account status.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.lastfm/
"""
import re

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pylast==2.1.0']

ATTR_LAST_PLAYED = 'last_played'
ATTR_PLAY_COUNT = 'play_count'
ATTR_TOP_PLAYED = 'top_played'

CONF_USERS = 'users'

ICON = 'mdi:lastfm'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_USERS, default=[]): vol.All(cv.ensure_list, [cv.string]),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Last.fm platform."""
    import pylast as lastfm
    network = lastfm.LastFMNetwork(api_key=config.get(CONF_API_KEY))

    add_devices(
        [LastfmSensor(
            username, network) for username in config.get(CONF_USERS)], True)


class LastfmSensor(Entity):
    """A class for the Last.fm account."""

    def __init__(self, user, lastfm):
        """Initialize the sensor."""
        self._user = lastfm.get_user(user)
        self._name = user
        self._lastfm = lastfm
        self._state = "Not Scrobbling"
        self._playcount = None
        self._lastplayed = None
        self._topplayed = None
        self._cover = None

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
        """Update device state."""
        self._cover = self._user.get_image()
        self._playcount = self._user.get_playcount()
        last = self._user.get_recent_tracks(limit=2)[0]
        self._lastplayed = "{} - {}".format(
            last.track.artist, last.track.title)
        top = self._user.get_top_tracks(limit=1)[0]
        toptitle = re.search("', '(.+?)',", str(top))
        topartist = re.search("'(.+?)',", str(top))
        self._topplayed = "{} - {}".format(
            topartist.group(1), toptitle.group(1))
        if self._user.get_now_playing() is None:
            self._state = "Not Scrobbling"
            return
        now = self._user.get_now_playing()
        self._state = "{} - {}".format(now.artist, now.title)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_LAST_PLAYED: self._lastplayed,
            ATTR_PLAY_COUNT: self._playcount,
            ATTR_TOP_PLAYED: self._topplayed,
        }

    @property
    def entity_picture(self):
        """Avatar of the user."""
        return self._cover

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON
