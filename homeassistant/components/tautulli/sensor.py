"""A platform which allows you to get information from Tautulli."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pytautulli import PyTautulliApiSession
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

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


def get_top_stats(coordinator: TautulliDataUpdateCoordinator, key: str) -> str | None:
    """Get top statistics."""
    value = None
    for stat in coordinator.home_stats:
        if stat.stat_id == key:
            value = stat.rows[0].title if stat.rows else None
        elif stat.stat_id == "top_users" and key == ATTR_TOP_USER:
            value = stat.rows[0].user if stat.rows else None
    return value


@dataclass
class TautulliSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Tautulli sensor."""

    value: Callable[[TautulliDataUpdateCoordinator, str], Any] = lambda val, _: val


SENSOR_TYPES: tuple[TautulliSensorEntityDescription, ...] = (
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="watching_count",
        name="Tautulli",
        native_unit_of_measurement="Watching",
        value=lambda coordinator, _: coordinator.activity.stream_count or 0
        if coordinator.activity
        else 0,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="stream_count",
        name="Streams",
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value=lambda coordinator, _: coordinator.activity.stream_count,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="stream_count_direct_play",
        name="Direct Plays",
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value=lambda coordinator, _: coordinator.activity.stream_count_direct_play,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="stream_count_direct_stream",
        name="Direct Streams",
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value=lambda coordinator, _: coordinator.activity.stream_count_direct_stream,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:plex",
        key="stream_count_transcode",
        name="Transcodes",
        native_unit_of_measurement="Streams",
        entity_registry_enabled_default=False,
        value=lambda coordinator, _: coordinator.activity.stream_count_transcode,
    ),
    TautulliSensorEntityDescription(
        key="total_bandwidth",
        name="Total Bandwidth",
        native_unit_of_measurement=DATA_KILOBITS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda coordinator, _: coordinator.activity.total_bandwidth,
    ),
    TautulliSensorEntityDescription(
        key="lan_bandwidth",
        name="LAN Bandwidth",
        native_unit_of_measurement=DATA_KILOBITS,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda coordinator, _: coordinator.activity.lan_bandwidth,
    ),
    TautulliSensorEntityDescription(
        key="wan_bandwidth",
        name="WAN Bandwidth",
        native_unit_of_measurement=DATA_KILOBITS,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda coordinator, _: coordinator.activity.wan_bandwidth,
    ),
    TautulliSensorEntityDescription(
        icon="mdi:movie-open",
        key="top_movies",
        name="Top Movie",
        entity_registry_enabled_default=False,
        value=lambda coordinator, key: get_top_stats(  # pylint: disable=unnecessary-lambda
            coordinator, key
        ),
    ),
    TautulliSensorEntityDescription(
        icon="mdi:television",
        key="top_tv",
        name="Top TV Show",
        entity_registry_enabled_default=False,
        value=lambda coordinator, key: get_top_stats(  # pylint: disable=unnecessary-lambda
            coordinator, key
        ),
    ),
    TautulliSensorEntityDescription(
        icon="mdi:walk",
        key=ATTR_TOP_USER,
        name="Top User",
        entity_registry_enabled_default=False,
        value=lambda coordinator, key: get_top_stats(  # pylint: disable=unnecessary-lambda
            coordinator, key
        ),
    ),
)


@dataclass
class TautulliSessionSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Tautulli sensor."""

    value: Callable[[PyTautulliApiSession], Any] = lambda val: val


SESSION_SENSOR_TYPES: tuple[TautulliSessionSensorEntityDescription, ...] = (
    TautulliSessionSensorEntityDescription(
        icon="mdi:plex",
        key="state",
        name="State",
        value=lambda user: user.state,
    ),
    TautulliSessionSensorEntityDescription(
        key="friendly_name",
        name="Friendly Name",
        entity_registry_enabled_default=False,
        value=lambda user: user.friendly_name,
    ),
    TautulliSessionSensorEntityDescription(
        key="full_title",
        name="Full Title",
        entity_registry_enabled_default=False,
        value=lambda user: user.full_title,
    ),
    TautulliSessionSensorEntityDescription(
        icon="mdi:progress-clock",
        key="progress",
        name="Progress",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        value=lambda user: user.progress_percent,
    ),
    TautulliSessionSensorEntityDescription(
        key="stream_resolution",
        name="Stream Resolution",
        entity_registry_enabled_default=False,
        value=lambda user: user.stream_video_resolution,
    ),
    TautulliSessionSensorEntityDescription(
        icon="mdi:plex",
        key="transcode_decision",
        name="Transcode Decision",
        entity_registry_enabled_default=False,
        value=lambda user: user.transcode_decision,
    ),
    TautulliSessionSensorEntityDescription(
        key="user_thumb",
        name="User Thumbnail",
        entity_registry_enabled_default=False,
        value=lambda user: user.user_thumb,
    ),
    TautulliSessionSensorEntityDescription(
        key="video_resolution",
        name="Video Resolution",
        entity_registry_enabled_default=False,
        value=lambda user: user.video_resolution,
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
    for user in coordinator.users:
        for description in SESSION_SENSOR_TYPES:
            _description = deepcopy(description)
            _description.key = f"{user.user_id}_{_description.key}"
            _description.name = f"{user.username} {_description.name}"
            entities.append(
                TautulliSessionSensor(
                    coordinator,
                    _description,
                    user.user_id,
                )
            )
    async_add_entities(entities)


class TautulliSensor(TautulliEntity, SensorEntity):
    """Representation of a Tautulli sensor."""

    entity_description: TautulliSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value(self.coordinator, self.entity_description.key)  # type: ignore[no-any-return]


class TautulliSessionSensor(TautulliEntity, SensorEntity):
    """Representation of a Tautulli session sensor."""

    entity_description: TautulliSessionSensorEntityDescription

    def __init__(
        self,
        coordinator: TautulliDataUpdateCoordinator,
        description: TautulliSessionSensorEntityDescription,
        user_id: int,
    ) -> None:
        """Initialize the Tautulli entity."""
        super().__init__(coordinator, description)
        self.user_id = user_id

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        for user in self.coordinator.activity.sessions:
            if user.user_id == self.user_id:
                return self.entity_description.value(user)  # type: ignore[no-any-return]
        return None
