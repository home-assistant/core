"""Sensor for Last.fm account status."""
from __future__ import annotations

import datetime
import hashlib
import logging
import re

import pylast as lastfm
from pylast import WSError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DOMAIN = "lastfm"

_LOGGER = logging.getLogger(__name__)

SERVICE_SCROBBLE = "scrobble"

ATTR_LAST_PLAYED = "last_played"
ATTR_PLAY_COUNT = "play_count"
ATTR_TOP_PLAYED = "top_played"

STATE_NOT_SCROBBLING = "Not Scrobbling"

CONF_USERS = "users"


ICON = "mdi:radio-fm"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_API_TOKEN): cv.string,
        vol.Required(CONF_USERS, default=[]): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Optional(CONF_PASSWORD, ""): cv.string,
                }
            ],
        ),
    }
)

ATTR_ARTIST = "artist"
ATTR_TITLE = "title"
ATTR_ALBUM = "album"
ATTR_TIMESTAMP = "timestamp"
SERVICE_SCHEMA_SCROBBLE = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_ARTIST): cv.string,
        vol.Required(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_ALBUM, ""): cv.string,
        vol.Optional(ATTR_TIMESTAMP, ""): cv.string,
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
    for user in users:
        try:
            lastfm_api.get_user(user["username"]).get_image()
            entities.append(LastfmSensor(user["username"], lastfm_api))
        except WSError as error:
            _LOGGER.error(error)
            return

    add_entities(entities, True)

    def scrobble(service: ServiceCall) -> None:
        """Call when a user adds a new Aftership tracking from HASS."""
        api_secret = config[CONF_API_TOKEN]
        entity_id = service.data[ATTR_ENTITY_ID]
        artist = service.data[ATTR_ARTIST]
        title = service.data[ATTR_TITLE]
        album = service.data[ATTR_ALBUM]
        timestamp = service.data[ATTR_TIMESTAMP]
        formatted_date = datetime.datetime.strptime(timestamp, "%Y/%m/%d %H:%M:%S")
        unix_timestamp = datetime.datetime.timestamp(formatted_date)

        for entity in entities:
            _LOGGER.error(entity.name)  # prints User1
            if entity.entity_id == entity_id:
                passwords = {d["username"]: d["password"] for d in users}

                try:
                    network = lastfm.LastFMNetwork(
                        api_key=api_key,
                        api_secret=api_secret,
                        username=entity.name,
                        password_hash=lastfm.md5(passwords[entity.name]),
                    )
                except WSError as error:
                    _LOGGER.error(error)
                    return

        # for entity in entities:
        #    if entity.entity_id == entity_id:
        network.scrobble(artist, title, int(unix_timestamp), album)

    hass.services.register(
        DOMAIN,
        SERVICE_SCROBBLE,
        scrobble,
        schema=SERVICE_SCHEMA_SCROBBLE,
    )


class LastfmSensor(SensorEntity):
    """A class for the Last.fm account."""

    _attr_attribution = "Data provided by Last.fm"

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
