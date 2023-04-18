"""Sensor for Last.fm account status."""
from __future__ import annotations

import hashlib
import logging
from typing import Final

from pylast import SIZE_SMALL, LastFMNetwork, Track, WSError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

LOGGER = logging.getLogger(__package__)
DOMAIN: Final = "lastfm"
DEFAULT_NAME = "LastFM"

CONF_USERS = "users"

ATTR_LAST_PLAYED = "last_played"
ATTR_PLAY_COUNT = "play_count"
ATTR_TOP_PLAYED = "top_played"

STATE_NOT_SCROBBLING = "Not Scrobbling"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_USERS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


def format_track(track: Track) -> str:
    """Format the track."""
    return f"{track.artist} - {track.title}"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Last.fm sensor platform."""
    lastfm_api = LastFMNetwork(api_key=config[CONF_API_KEY])
    async_add_entities(
        (LastFmSensor(user, lastfm_api) for user in config[CONF_USERS]), True
    )


class LastFmSensor(SensorEntity):
    """A class for the Last.fm account."""

    _attr_attribution = "Data provided by Last.fm"
    _attr_icon = "mdi:radio-fm"

    def __init__(self, user: str, lastfm_api: LastFMNetwork) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = hashlib.sha256(user.encode("utf-8")).hexdigest()
        self._attr_name = user
        try:
            self._user = lastfm_api.get_user(user)
        except WSError as exc:
            LOGGER.error(exc)

    def update(self) -> None:
        """Update device state."""
        self._attr_entity_picture = self._user.get_image(SIZE_SMALL)
        if self._user.get_now_playing() is not None:
            self._attr_native_value = format_track(self._user.get_now_playing())
        else:
            self._attr_native_value = STATE_NOT_SCROBBLING
        top_played = None
        if top_tracks := self._user.get_top_tracks(limit=1):
            top_played = format_track(top_tracks[0].item)
        last_played = format_track(self._user.get_recent_tracks(limit=1)[0].track)
        play_count = self._user.get_playcount()
        self._attr_extra_state_attributes = {
            ATTR_LAST_PLAYED: last_played,
            ATTR_PLAY_COUNT: play_count,
            ATTR_TOP_PLAYED: top_played,
        }
