"""A platform which allows you to get information from Tautulli."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.components.tautulli.coordinator import TautulliDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import CONF_MONITORED_USERS, TautulliEntity
from .const import (
    DATA_KEY_COORDINATOR,
    DEFAULT_NAME,
    DEFAULT_PATH,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

# Deprecated in Home Assistant 2021.11
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_MONITORED_USERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tautulli sensor."""
    entities = [
        TautulliSensor(
            hass.data[DOMAIN][entry.entry_id][DATA_KEY_COORDINATOR],
            entry.data.get(CONF_NAME, DEFAULT_NAME),
            entry.options[CONF_MONITORED_USERS],
            entry.entry_id,
        )
    ]

    async_add_entities(entities, True)


class TautulliSensor(TautulliEntity, SensorEntity):
    """Representation of a Tautulli sensor."""

    _attr_icon = "mdi:plex"
    _attr_native_unit_of_measurement = "Watching"
    coordinator: TautulliDataUpdateCoordinator

    def __init__(
        self,
        coordinator: TautulliDataUpdateCoordinator,
        name: str,
        users: list,
        server_unique_id: str,
    ) -> None:
        """Initialize the Tautulli sensor."""
        super().__init__(coordinator, name, server_unique_id)
        self._attr_unique_id = f"{server_unique_id}/{name}"
        self.usernames = users
        self._attr_name = name

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.activity:
            return 0
        return self.coordinator.activity.stream_count or 0

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return attributes for the sensor."""
        if (
            not self.coordinator.activity
            or not self.coordinator.home_stats
            or not self.coordinator.users
        ):
            return None

        _attributes = {
            "stream_count": self.coordinator.activity.stream_count,
            "stream_count_direct_play": self.coordinator.activity.stream_count_direct_play,
            "stream_count_direct_stream": self.coordinator.activity.stream_count_direct_stream,
            "stream_count_transcode": self.coordinator.activity.stream_count_transcode,
            "total_bandwidth": self.coordinator.activity.total_bandwidth,
            "lan_bandwidth": self.coordinator.activity.lan_bandwidth,
            "wan_bandwidth": self.coordinator.activity.wan_bandwidth,
        }

        for stat in self.coordinator.home_stats:
            if stat.stat_id == "top_movies":
                _attributes["Top Movie"] = stat.rows[0].title if stat.rows else None
            elif stat.stat_id == "top_tv":
                _attributes["Top TV Show"] = stat.rows[0].title if stat.rows else None
            elif stat.stat_id == "top_users":
                _attributes["Top User"] = stat.rows[0].user if stat.rows else None

        for user in self.coordinator.users:
            if (
                self.usernames
                and user.username not in self.usernames
                or user.username == "Local"
            ):
                continue
            _attributes.setdefault(user.username, {})["Activity"] = None

        for session in self.coordinator.activity.sessions:
            if not _attributes.get(session.username):
                continue

            _attributes[session.username]["Activity"] = session.state

        return _attributes
