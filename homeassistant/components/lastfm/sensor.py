"""Sensor for Last.fm account status."""
from __future__ import annotations

import hashlib
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
from .coordinator import LastFMDataUpdateCoordinator, LastFMUserData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize the entries."""

    coordinator: LastFMDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        (
            LastFmSensor(coordinator, username, entry.entry_id)
            for username in entry.options[CONF_USERS]
        ),
    )


class LastFmSensor(CoordinatorEntity[LastFMDataUpdateCoordinator], SensorEntity):
    """A class for the Last.fm account."""

    _attr_attribution = "Data provided by Last.fm"
    _attr_icon = "mdi:radio-fm"
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
    def available(self) -> bool:
        """If user not found in coordinator, entity is unavailable."""
        return super().available and self.user_data is not None

    @property
    def entity_picture(self) -> str | None:
        """Return user avatar."""
        if self.user_data and self.user_data.image is not None:
            return self.user_data.image
        return None

    @property
    def native_value(self) -> str:
        """Return value of sensor."""
        if self.user_data and self.user_data.now_playing is not None:
            return self.user_data.now_playing
        return STATE_NOT_SCROBBLING

    @property
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
