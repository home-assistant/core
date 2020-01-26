"""Sensor for Last.fm account status."""
import logging
import re
import hashlib

import pylast as lastfm
from pylast import WSError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_API_KEY
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_PLAYED = "last_played"
ATTR_PLAY_COUNT = "play_count"
ATTR_TOP_PLAYED = "top_played"
ATTRIBUTION = "Data provided by Last.fm"

CONF_USERS = "users"

ICON = "mdi:lastfm"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_USERS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Last.fm sensor platform."""
    api_key = config[CONF_API_KEY]
    users = config.get(CONF_USERS)

    lastfm_api = lastfm.LastFMNetwork(api_key=api_key)

    entities = []
    for username in users:
        try:
            lastfm_api.get_user(username).get_image()
            entities.append(LastfmSensor(username, lastfm_api))
        except WSError as error:
            _LOGGER.error(error)
            return

    add_entities(entities, True)


class LastfmSensor(Entity):
    """A class for the Last.fm account."""

    def __init__(self, user, lastfm_api):
        """Initialize the sensor."""
        self._unique_id = hashlib.sha256(str(user).encode("utf-8")).hexdigest()
        self._user = lastfm_api.get_user(user)
        self._name = user
        self._entity_id = self.__generate_entity_id(user)
        self._lastfm = lastfm_api
        self._state = "Not Scrobbling"
        self._playcount = None
        self._lastplayed = None
        self._topplayed = None
        self._cover = None

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def entity_id(self):
        """Return the entity ID."""
        return f"sensor.lastfm_{self._entity_id}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update device state."""
        self._cover = self._user.get_image()
        self._playcount = self._user.get_playcount()
        last = self._user.get_recent_tracks(limit=2)[0]
        self._lastplayed = f"{last.track.artist} - {last.track.title}"
        top = self._user.get_top_tracks(limit=1)[0]
        toptitle = re.search("', '(.+?)',", str(top))
        topartist = re.search("'(.+?)',", str(top))
        self._topplayed = "{} - {}".format(topartist.group(1), toptitle.group(1))
        if self._user.get_now_playing() is None:
            self._state = "Not Scrobbling"
            return
        now = self._user.get_now_playing()
        self._state = f"{now.artist} - {now.title}"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
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

    def __generate_entity_id(user):
        """Generate the entity_id for this sensor."""
        return user
