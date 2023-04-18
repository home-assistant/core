"""Sensor for Last.fm account status."""
from __future__ import annotations

import hashlib

from pylast import SIZE_SMALL, Track, User
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from .const import (
    ATTR_LAST_PLAYED,
    ATTR_PLAY_COUNT,
    ATTR_TOP_PLAYED,
    CONF_USERS,
    DOMAIN,
    STATE_NOT_SCROBBLING,
)
from .coordinator import LastFmUpdateCoordinator
from .entity import LastFmEntity

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
    """Set up the LastFM sensor from yaml."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize the entries."""
    async_add_entities(
        LastFmSensor(hass.data[DOMAIN][entry.entry_id], user)
        for user in entry.data[CONF_USERS]
    )


class LastFmSensor(LastFmEntity, SensorEntity):
    """A class for the Last.fm account."""

    def __init__(self, coordinator: LastFmUpdateCoordinator, user: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = hashlib.sha256(user.encode("utf-8")).hexdigest()
        self.entity_description = SensorEntityDescription(
            key=user, name=f"LastFM {user}", icon="mdi:radio-fm"
        )

    def _user(self) -> User:
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def native_value(self) -> StateType:
        """Return what the user is scrobbling."""
        if user := self._user():
            if user.get_now_playing() is not None:
                return format_track(user.get_now_playing())
        return STATE_NOT_SCROBBLING

    @property
    def entity_picture(self):
        """Avatar of the user."""
        return self._user().get_image(SIZE_SMALL)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        top_played = None
        if top_tracks := self._user().get_top_tracks(limit=1):
            top_played = format_track(top_tracks[0].item)
        return {
            ATTR_LAST_PLAYED: format_track(
                self._user().get_recent_tracks(limit=1)[0].track
            ),
            ATTR_PLAY_COUNT: self._user().get_playcount(),
            ATTR_TOP_PLAYED: top_played,
        }
