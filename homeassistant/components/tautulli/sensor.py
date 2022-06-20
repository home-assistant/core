"""A platform which allows you to get information from Tautulli."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pytautulli import (
    PyTautulliApiActivity,
    PyTautulliApiHomeStats,
    PyTautulliApiSession,
    PyTautulliApiUser,
)
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    DATA_KILOBITS,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import EntityCategory, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TautulliEntity
from .const import (
    ATTR_TOP_USER,
    CONF_MONITORED_USERS,
    DEFAULT_NAME,
    DEFAULT_PATH,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .coordinator import TautulliDataUpdateCoordinator

# Deprecated in Home Assistant 2022.4
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


def get_top_stats(
    home_stats: PyTautulliApiHomeStats, activity: PyTautulliApiActivity, key: str
) -> str | None:
    """Get top statistics."""
    value = None
    for stat in home_stats:
        if stat.rows and stat.stat_id == key:
            value = stat.rows[0].title
        elif stat.rows and stat.stat_id == "top_users" and key == ATTR_TOP_USER:
            value = stat.rows[0].user
    return value


@dataclass
class TautulliSensorEntityMixin:
    """Mixin for Tautulli sensor."""

    value_fn: Callable[[PyTautulliApiHomeStats, PyTautulliApiActivity, str], Any]


@dataclass
class TautulliSensorEntityDescription(
    SensorEntityDescription, TautulliSensorEntityMixin
):
    """Describes a Tautulli sensor."""


SENSOR_TYPES: tuple[TautulliSensorEntityDescription, ...] = (
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="watching_count",
        name="Tautulli",
        native_unit_of_measurement="Watching",
        value_fn=lambda home_stats, activity, _: activity.stream_count,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="stream_count_direct_play",
        name="Direct Plays",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value_fn=lambda home_stats, activity, _: activity.stream_count_direct_play,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="stream_count_direct_stream",
        name="Direct Streams",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value_fn=lambda home_stats, activity, _: activity.stream_count_direct_stream
        or 0,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="stream_count_transcode",
        name="Transcodes",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value_fn=lambda home_stats, activity, _: activity.stream_count_transcode,
    ),
    TautulliSensorEntityDescription(
        key="total_bandwidth",
        name="Total Bandwidth",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_KILOBITS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda home_stats, activity, _: activity.total_bandwidth,
    ),
    TautulliSensorEntityDescription(
        key="lan_bandwidth",
        name="LAN Bandwidth",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_KILOBITS,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda home_stats, activity, _: activity.lan_bandwidth,
    ),
    TautulliSensorEntityDescription(
        key="wan_bandwidth",
        name="WAN Bandwidth",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_KILOBITS,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda home_stats, activity, _: activity.wan_bandwidth,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:movie-open",
        key="top_movies",
        name="Top Movie",
        entity_registry_enabled_default=False,
        value_fn=get_top_stats,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:television",
        key="top_tv",
        name="Top TV Show",
        entity_registry_enabled_default=False,
        value_fn=get_top_stats,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:walk",
        key=ATTR_TOP_USER,
        name="Top User",
        entity_registry_enabled_default=False,
        value_fn=get_top_stats,
    ),
)


@dataclass
class TautulliSessionSensorEntityMixin:
    """Mixin for Tautulli session sensor."""

    value_fn: Callable[[PyTautulliApiSession], Any]


@dataclass
class TautulliSessionSensorEntityDescription(
    SensorEntityDescription, TautulliSessionSensorEntityMixin
):
    """Describes a Tautulli session sensor."""


SESSION_SENSOR_TYPES: tuple[TautulliSessionSensorEntityDescription, ...] = (
    TautulliSessionSensorEntityDescription(
        icon="mdi:plex",
        key="state",
        name="State",
        value_fn=lambda session: session.state,
    ),
    TautulliSessionSensorEntityDescription(
        key="full_title",
        name="Full Title",
        entity_registry_enabled_default=False,
        value_fn=lambda session: session.full_title,
    ),
    TautulliSessionSensorEntityDescription(
        icon="mdi:progress-clock",
        key="progress",
        name="Progress",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        value_fn=lambda session: session.progress_percent,
    ),
    TautulliSessionSensorEntityDescription(
        key="stream_resolution",
        name="Stream Resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda session: session.stream_video_resolution,
    ),
    TautulliSessionSensorEntityDescription(
        icon="mdi:plex",
        key="transcode_decision",
        name="Transcode Decision",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda session: session.transcode_decision,
    ),
    TautulliSessionSensorEntityDescription(
        key="session_thumb",
        name="session Thumbnail",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda session: session.user_thumb,
    ),
    TautulliSessionSensorEntityDescription(
        key="video_resolution",
        name="Video Resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda session: session.video_resolution,
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create the Tautulli sensor."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tautulli sensor."""
    coordinator: TautulliDataUpdateCoordinator = hass.data[DOMAIN]
    entities: list[TautulliSensor | TautulliSessionSensor] = [
        TautulliSensor(
            coordinator,
            description,
        )
        for description in SENSOR_TYPES
    ]
    if coordinator.users:
        entities.extend(
            TautulliSessionSensor(
                coordinator,
                description,
                user,
            )
            for description in SESSION_SENSOR_TYPES
            for user in coordinator.users
            if user.username != "Local"
        )
    async_add_entities(entities)


class TautulliSensor(TautulliEntity, SensorEntity):
    """Representation of a Tautulli sensor."""

    entity_description: TautulliSensorEntityDescription

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.home_stats,
            self.coordinator.activity,
            self.entity_description.key,
        )


class TautulliSessionSensor(TautulliEntity, SensorEntity):
    """Representation of a Tautulli session sensor."""

    entity_description: TautulliSessionSensorEntityDescription

    def __init__(
        self,
        coordinator: TautulliDataUpdateCoordinator,
        description: EntityDescription,
        user: PyTautulliApiUser,
    ) -> None:
        """Initialize the Tautulli entity."""
        super().__init__(coordinator, description, user)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{user.user_id}_{description.key}"
        self._attr_name = f"{user.username} {description.name}"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.activity:
            for session in self.coordinator.activity.sessions:
                if self.user and session.user_id == self.user.user_id:
                    return self.entity_description.value_fn(session)
        return None
