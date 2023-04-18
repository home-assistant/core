"""Sensor for Last.fm account status."""
from __future__ import annotations

import hashlib
import logging

from pylast import SIZE_SMALL, Track
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_LAST_PLAYED,
    ATTR_PLAY_COUNT,
    ATTR_TOP_PLAYED,
    CONF_USERS,
    STATE_NOT_SCROBBLING,
)
from .coordinator import LastFmUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_USERS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


def format_track(track: Track) -> str:
    """Format the track."""
    return f"{track.artist} - {track.title}"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Last.fm sensor platform."""
    coordinator = LastFmUpdateCoordinator(hass, config)
    add_entities((LastFmSensor(coordinator, user) for user in config[CONF_USERS]), True)


class LastFmSensor(CoordinatorEntity[LastFmUpdateCoordinator], SensorEntity):
    """A class for the Last.fm account."""

    _attr_attribution = "Data provided by Last.fm"
    _attr_icon = "mdi:radio-fm"

    def __init__(self, coordinator: LastFmUpdateCoordinator, user: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = hashlib.sha256(user.encode("utf-8")).hexdigest()
        self._attr_name = user
        self._attr_native_value = STATE_NOT_SCROBBLING

    @callback
    def _handle_coordinator_update(self) -> None:
        if user := self.coordinator.data.get(self.entity_description.key):
            self._attr_entity_picture = user.get_image(SIZE_SMALL)
            if user.get_now_playing() is not None:
                self._attr_native_value = format_track(user.get_now_playing())
            else:
                self._attr_native_value = STATE_NOT_SCROBBLING
            top_played = None
            if top_tracks := user.get_top_tracks(limit=1):
                top_played = format_track(top_tracks[0].item)
            self._attr_extra_state_attributes = {
                ATTR_LAST_PLAYED: format_track(
                    user.get_recent_tracks(limit=1)[0].track
                ),
                ATTR_PLAY_COUNT: user.get_playcount(),
                ATTR_TOP_PLAYED: top_played,
            }
