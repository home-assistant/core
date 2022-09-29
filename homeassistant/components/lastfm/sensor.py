"""Sensor for Last.fm account status."""
from __future__ import annotations

import hashlib
import logging
import re

import pylast as lastfm
from pylast import WSError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION, CONF_API_KEY
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_PLAYED = "last_played"
ATTR_PLAY_COUNT = "play_count"
ATTR_TOP_PLAYED = "top_played"
ATTRIBUTION = "Data provided by Last.fm"

STATE_NOT_SCROBBLING = "Not Scrobbling"

CONF_USERS = "users"

ICON = "mdi:radio-fm"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_USERS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Last.fm sensor platform."""
    api_key = config[CONF_API_KEY]
    users = config[CONF_USERS]

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


class LastfmSensor(SensorEntity):
    """A class for the Last.fm account."""

    def __init__(self, user, lastfm_api):
        """Initialize the sensor."""
        self._unique_id = hashlib.sha256(user.encode("utf-8")).hexdigest()
        self._user = lastfm_api.get_user(user)
        self._name = user
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
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Update device state."""
        self._cover = self._user.get_image()
        self._playcount = self._user.get_playcount()

        if recent_tracks := self._user.get_recent_tracks(limit=2):
            last = recent_tracks[0]
            self._lastplayed = f"{last.track.artist} - {last.track.title}"

        if top_tracks := self._user.get_top_tracks(limit=1):
            top = str(top_tracks[0])
            if (toptitle := re.search("', '(.+?)',", top)) and (
                topartist := re.search("'(.+?)',", top)
            ):
                self._topplayed = f"{topartist.group(1)} - {toptitle.group(1)}"

        if (now_playing := self._user.get_now_playing()) is None:
            self._state = STATE_NOT_SCROBBLING
            return

        self._state = f"{now_playing.artist} - {now_playing.title}"

    @property
    def extra_state_attributes(self):
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
