"""Sensor for Last.fm account status."""

from datetime import datetime, timedelta
from functools import partial
import hashlib
from typing import Any, override

from pylast import PyLastError

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_LAST_PLAYED,
    ATTR_PLAY_COUNT,
    ATTR_TOP_PLAYED,
    CONF_USERS,
    DEFAULT_NAME,
    DOMAIN,
    STATE_NOT_SCROBBLING,
)
from .coordinator import LastFMConfigEntry, LastFMDataUpdateCoordinator, LastFMUserData


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


class LastFmSensor(CoordinatorEntity[LastFMDataUpdateCoordinator], SensorEntity):
    """A class for the Last.fm account."""

    _attr_attribution = "Data provided by Last.fm"
    _attr_translation_key = "lastfm"
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: LastFMDataUpdateCoordinator,
        username: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._username = username
        self._attr_unique_id = hashlib.sha256(username.encode("utf-8")).hexdigest()
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.last.fm",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{entry_id}_{self._attr_unique_id}")},
            manufacturer=DEFAULT_NAME,
            name=f"{DEFAULT_NAME} {username}",
        )

    @property
    def user_data(self) -> LastFMUserData | None:
        """Returns the user from the coordinator."""
        return self.coordinator.data.get(self._username)

    @property
    @override
    def available(self) -> bool:
        """If user not found in coordinator, entity is unavailable."""
        return super().available and self.user_data is not None

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

    async def async_scrobble(
        self,
        artist: str,
        title: str,
        album: str | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Scrobble a track for this sensor's Last.fm user."""
        client = self.coordinator.get_scrobble_client(self._username)
        if client is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="user_not_authorized",
                translation_placeholders={"username": self._username},
            )

        now = dt_util.utcnow()
        if timestamp is None:
            scrobble_time = now
        else:
            if timestamp.tzinfo is None:  # the datetime selector gives local time
                timestamp = timestamp.replace(tzinfo=dt_util.get_default_time_zone())
            scrobble_time = timestamp
        if scrobble_time > now or scrobble_time < now - timedelta(days=14):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="timestamp_out_of_range"
            )

        try:
            await self.hass.async_add_executor_job(
                partial(
                    client.scrobble,
                    artist=artist,
                    title=title,
                    timestamp=int(scrobble_time.timestamp()),
                    album=album,
                )
            )
        except PyLastError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="scrobble_failed",
            ) from err
