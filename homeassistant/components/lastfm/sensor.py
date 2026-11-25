"""Sensor for Last.fm account status."""

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
from typing import Any, override

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import MAX_LENGTH_STATE_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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


@dataclass(frozen=True, kw_only=True)
class LastFMSensorEntityDescription(SensorEntityDescription):
    """Describes a Last.fm sensor entity."""

    value_fn: Callable[[LastFMUserData], StateType]
    picture_fn: Callable[[LastFMUserData], str | None] = lambda _: None


SENSOR_TYPES: tuple[LastFMSensorEntityDescription, ...] = (
    LastFMSensorEntityDescription(
        key="last_played",
        translation_key="last_played",
        value_fn=lambda data: data.last_track,
        picture_fn=lambda data: data.last_track_image,
    ),
    LastFMSensorEntityDescription(
        key="top_track",
        translation_key="top_track",
        value_fn=lambda data: data.top_track,
        picture_fn=lambda data: data.top_track_image,
    ),
    LastFMSensorEntityDescription(
        key="play_count",
        translation_key="play_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.play_count,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LastFMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize the entries."""

    coordinator = entry.runtime_data
    entities: list[LastFmEntity] = []
    for username in entry.options[CONF_USERS]:
        entities.append(LastFmSensor(coordinator, username, entry.entry_id))
        entities.extend(
            LastFmUserSensor(coordinator, username, entry.entry_id, description)
            for description in SENSOR_TYPES
        )
    async_add_entities(entities)


class LastFmEntity(CoordinatorEntity[LastFMDataUpdateCoordinator], SensorEntity):
    """Base class for Last.fm user entities."""

    _attr_attribution = "Data provided by Last.fm"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LastFMDataUpdateCoordinator,
        username: str,
        entry_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._username = username
        self._user_hash = hashlib.sha256(username.encode("utf-8")).hexdigest()
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.last.fm",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{entry_id}_{self._user_hash}")},
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


class LastFmSensor(LastFmEntity):
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
        """Return album art of the playing track, or the user avatar."""
        if self.user_data is None:
            return None
        return self.user_data.now_playing_image or self.user_data.image

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


class LastFmUserSensor(LastFmEntity):
    """A Last.fm sensor for a single piece of user data."""

    entity_description: LastFMSensorEntityDescription

    def __init__(
        self,
        coordinator: LastFMDataUpdateCoordinator,
        username: str,
        entry_id: str,
        description: LastFMSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, username, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._user_hash}_{description.key}"

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the album art of the track."""
        if self.user_data is None:
            return None
        return self.entity_description.picture_fn(self.user_data)

    @property
    @override
    def native_value(self) -> StateType:
        """Return value of sensor."""
        if self.user_data is None:
            return None
        value = self.entity_description.value_fn(self.user_data)
        return value[:MAX_LENGTH_STATE_STATE] if isinstance(value, str) else value
