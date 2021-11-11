"""A platform which allows you to get information from Tautulli."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PATH,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType, StateType

from . import TautulliEntity
from .const import (
    CONF_MONITORED_USERS,
    DATA_KEY_COORDINATOR,
    DEFAULT_NAME,
    DEFAULT_PATH,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .coordinator import TautulliDataUpdateCoordinator

# Deprecated in Home Assistant 2021.12
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

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        icon="mdi:plex",
        key="tautulli",
        name="Tautulli",
        native_unit_of_measurement="Watching",
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: entity_platform.AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Modem Caller ID component."""
    if CONF_MONITORED_CONDITIONS in config:
        config.pop(CONF_MONITORED_CONDITIONS)
    if CONF_MONITORED_USERS in config:
        config.pop(CONF_MONITORED_USERS)
    if CONF_NAME in config:
        config.pop(CONF_NAME)
    if CONF_PORT in config:
        port = config[CONF_PORT]
        config.pop(CONF_PORT)
    if CONF_PATH in config:
        path = config[CONF_PATH]
        config.pop(CONF_PATH)
    protocol = f"http{'s' if config.get(CONF_SSL) else ''}"
    config[CONF_URL] = f"{protocol}://{config[CONF_HOST]}:{port or '8181'}{path or ''}"
    config.pop(CONF_HOST)
    config.pop(CONF_PLATFORM)
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tautulli sensor."""
    sensors = [
        TautulliSensor(
            hass.data[DOMAIN][entry.entry_id][DATA_KEY_COORDINATOR],
            description,
            entry.entry_id,
        )
        for description in SENSOR_TYPES
    ]

    async_add_entities(sensors, True)


class TautulliSensor(TautulliEntity, SensorEntity):
    """Representation of a Tautulli sensor."""

    coordinator: TautulliDataUpdateCoordinator

    def __init__(
        self,
        coordinator: TautulliDataUpdateCoordinator,
        description: SensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the Tautulli sensor."""
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}/{description.name}"
        self._attr_name = description.name

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
            if user.username == "Local":
                continue
            _attributes.setdefault(user.username, {})["Activity"] = None

        for session in self.coordinator.activity.sessions:
            if not _attributes.get(session.username) or "null" in session.state:
                continue

            _attributes[session.username]["Activity"] = session.state

        return _attributes
