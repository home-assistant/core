"""A platform which allows you to get information from Tautulli."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from pytautulli import (
    PyTautulliApiActivity,
    PyTautulliApiHomeStats,
    PyTautulliApiSession,
    PyTautulliApiUser,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import TautulliEntity
from .const import ATTR_TOP_USER, DOMAIN
from .coordinator import TautulliDataUpdateCoordinator


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

    value_fn: Callable[[PyTautulliApiHomeStats, PyTautulliApiActivity, str], StateType]


@dataclass
class TautulliSensorEntityDescription(
    SensorEntityDescription, TautulliSensorEntityMixin
):
    """Describes a Tautulli sensor."""


SENSOR_TYPES: tuple[TautulliSensorEntityDescription, ...] = (
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="watching_count",
        name="Watching",
        native_unit_of_measurement="Watching",
        value_fn=lambda home_stats, activity, _: cast(int, activity.stream_count),
    ),
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="stream_count_direct_play",
        name="Direct plays",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value_fn=lambda home_stats, activity, _: cast(
            int, activity.stream_count_direct_play
        ),
    ),
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="stream_count_direct_stream",
        name="Direct streams",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value_fn=lambda home_stats, activity, _: cast(
            int, activity.stream_count_direct_stream
        ),
    ),
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="stream_count_transcode",
        name="Transcodes",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value_fn=lambda home_stats, activity, _: cast(
            int, activity.stream_count_transcode
        ),
    ),
    TautulliSensorEntityDescription(
        key="total_bandwidth",
        name="Total bandwidth",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.KILOBITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda home_stats, activity, _: cast(int, activity.total_bandwidth),
    ),
    TautulliSensorEntityDescription(
        key="lan_bandwidth",
        name="LAN bandwidth",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.KILOBITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda home_stats, activity, _: cast(int, activity.lan_bandwidth),
    ),
    TautulliSensorEntityDescription(
        key="wan_bandwidth",
        name="WAN bandwidth",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.KILOBITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda home_stats, activity, _: cast(int, activity.wan_bandwidth),
    ),
    TautulliSensorEntityDescription(
        icon="mdi:movie-open",
        key="top_movies",
        name="Top movie",
        entity_registry_enabled_default=False,
        value_fn=get_top_stats,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:television",
        key="top_tv",
        name="Top TV show",
        entity_registry_enabled_default=False,
        value_fn=get_top_stats,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:walk",
        key=ATTR_TOP_USER,
        name="Top user",
        entity_registry_enabled_default=False,
        value_fn=get_top_stats,
    ),
)


@dataclass
class TautulliSessionSensorEntityMixin:
    """Mixin for Tautulli session sensor."""

    value_fn: Callable[[PyTautulliApiSession], StateType]


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
        value_fn=lambda session: cast(str, session.state),
    ),
    TautulliSessionSensorEntityDescription(
        key="full_title",
        name="Full title",
        entity_registry_enabled_default=False,
        value_fn=lambda session: cast(str, session.full_title),
    ),
    TautulliSessionSensorEntityDescription(
        icon="mdi:progress-clock",
        key="progress",
        name="Progress",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        value_fn=lambda session: cast(str, session.progress_percent),
    ),
    TautulliSessionSensorEntityDescription(
        key="stream_resolution",
        name="Stream resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda session: cast(str, session.stream_video_resolution),
    ),
    TautulliSessionSensorEntityDescription(
        icon="mdi:plex",
        key="transcode_decision",
        name="Transcode decision",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda session: cast(str, session.transcode_decision),
    ),
    TautulliSessionSensorEntityDescription(
        key="session_thumb",
        name="session thumbnail",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda session: cast(str, session.user_thumb),
    ),
    TautulliSessionSensorEntityDescription(
        key="video_resolution",
        name="Video resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda session: cast(str, session.video_resolution),
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
    coordinator: TautulliDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
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
    def native_value(self) -> StateType:
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

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.coordinator.activity:
            for session in self.coordinator.activity.sessions:
                if self.user and session.user_id == self.user.user_id:
                    return self.entity_description.value_fn(session)
        return None
