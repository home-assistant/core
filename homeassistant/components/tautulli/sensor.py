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
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import TautulliConfigEntry, TautulliEntity
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


@dataclass(frozen=True, kw_only=True)
class TautulliSensorEntityDescription(SensorEntityDescription):
    """Describes a Tautulli sensor."""

    value_fn: Callable[[PyTautulliApiHomeStats, PyTautulliApiActivity, str], StateType]


SENSOR_TYPES: tuple[TautulliSensorEntityDescription, ...] = (
    TautulliSensorEntityDescription(
        key="watching_count",
        translation_key="watching_count",
        native_unit_of_measurement="Watching",
        value_fn=lambda home_stats, activity, _: cast(int, activity.stream_count),
    ),
    TautulliSensorEntityDescription(
        key="stream_count_direct_play",
        translation_key="stream_count_direct_play",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value_fn=lambda home_stats, activity, _: cast(
            int, activity.stream_count_direct_play
        ),
    ),
    TautulliSensorEntityDescription(
        key="stream_count_direct_stream",
        translation_key="stream_count_direct_stream",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value_fn=lambda home_stats, activity, _: cast(
            int, activity.stream_count_direct_stream
        ),
    ),
    TautulliSensorEntityDescription(
        key="stream_count_transcode",
        translation_key="stream_count_transcode",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value_fn=lambda home_stats, activity, _: cast(
            int, activity.stream_count_transcode
        ),
    ),
    TautulliSensorEntityDescription(
        key="total_bandwidth",
        translation_key="total_bandwidth",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.KILOBITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda home_stats, activity, _: cast(int, activity.total_bandwidth),
    ),
    TautulliSensorEntityDescription(
        key="lan_bandwidth",
        translation_key="lan_bandwidth",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.KILOBITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda home_stats, activity, _: cast(int, activity.lan_bandwidth),
    ),
    TautulliSensorEntityDescription(
        key="wan_bandwidth",
        translation_key="wan_bandwidth",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.KILOBITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda home_stats, activity, _: cast(int, activity.wan_bandwidth),
    ),
    TautulliSensorEntityDescription(
        key="top_movies",
        translation_key="top_movies",
        entity_registry_enabled_default=False,
        value_fn=get_top_stats,
    ),
    TautulliSensorEntityDescription(
        key="top_tv",
        translation_key="top_tv",
        entity_registry_enabled_default=False,
        value_fn=get_top_stats,
    ),
    TautulliSensorEntityDescription(
        key=ATTR_TOP_USER,
        translation_key="top_user",
        entity_registry_enabled_default=False,
        value_fn=get_top_stats,
    ),
)


@dataclass(frozen=True, kw_only=True)
class TautulliSessionSensorEntityDescription(SensorEntityDescription):
    """Describes a Tautulli session sensor."""

    value_fn: Callable[[PyTautulliApiSession], StateType]


SESSION_SENSOR_TYPES: tuple[TautulliSessionSensorEntityDescription, ...] = (
    TautulliSessionSensorEntityDescription(
        key="state",
        translation_key="state",
        value_fn=lambda session: cast(str, session.state),
    ),
    TautulliSessionSensorEntityDescription(
        key="full_title",
        translation_key="full_title",
        entity_registry_enabled_default=False,
        value_fn=lambda session: cast(str, session.full_title),
    ),
    TautulliSessionSensorEntityDescription(
        key="progress",
        translation_key="progress",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        value_fn=lambda session: cast(str, session.progress_percent),
    ),
    TautulliSessionSensorEntityDescription(
        key="stream_resolution",
        translation_key="stream_resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda session: cast(str, session.stream_video_resolution),
    ),
    TautulliSessionSensorEntityDescription(
        key="transcode_decision",
        translation_key="transcode_decision",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda session: cast(str, session.transcode_decision),
    ),
    TautulliSessionSensorEntityDescription(
        key="session_thumb",
        translation_key="session_thumb",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda session: cast(str, session.user_thumb),
    ),
    TautulliSessionSensorEntityDescription(
        key="video_resolution",
        translation_key="video_resolution",
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
    hass: HomeAssistant,
    entry: TautulliConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tautulli sensor."""
    data = entry.runtime_data
    entities: list[TautulliSensor | TautulliSessionSensor] = [
        TautulliSensor(
            data,
            description,
        )
        for description in SENSOR_TYPES
    ]
    if data.users:
        entities.extend(
            TautulliSessionSensor(
                data,
                description,
                user,
            )
            for description in SESSION_SENSOR_TYPES
            for user in data.users
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
