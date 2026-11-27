"""Sensor for Last.fm account status."""

from typing import Any, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_LAST_PLAYED,
    ATTR_PLAY_COUNT,
    ATTR_TOP_PLAYED,
    CONF_USERS,
    STATE_NOT_SCROBBLING,
)
from .coordinator import LastFMConfigEntry, LastFMDataUpdateCoordinator
from .entity import LastFmEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LastFMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize the entries."""

    coordinator = entry.runtime_data
    async_add_entities(
        (
            LastFmSensor(coordinator, username, entry.entry_id)
            for username in entry.options[CONF_USERS]
        ),
    )


class LastFmSensor(LastFmEntity, SensorEntity):
    """A class for the Last.fm account."""

    _attr_translation_key = "lastfm"
    _attr_name = None

    def __init__(
        self,
        coordinator: LastFMDataUpdateCoordinator,
        username: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, username, entry_id)
        self._attr_unique_id = self._user_hash

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return user avatar."""
        if self.user_data and self.user_data.image is not None:
            return self.user_data.image
        return None

    @property
    @override
    def native_value(self) -> str:
        """Return value of sensor."""
        if self.user_data and self.user_data.now_playing is not None:
            return self.user_data.now_playing
        return STATE_NOT_SCROBBLING

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return state attributes."""
        play_count = None
        last_track = None
        top_track = None
        if self.user_data:
            play_count = self.user_data.play_count
            last_track = self.user_data.last_track
            top_track = self.user_data.top_track
        return {
            ATTR_PLAY_COUNT: play_count,
            ATTR_LAST_PLAYED: last_track,
            ATTR_TOP_PLAYED: top_track,
        }
