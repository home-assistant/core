"""Platform for sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
from typing import cast

from geocachingapi.models import GeocachingCache, GeocachingStatus, GeocachingTrackable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, GEOCACHING_ID_SENSOR_FORMAT, GeocacheCategory
from .coordinator import GeocachingDataUpdateCoordinator
from .device_tracker import GeoEntityCacheLocation, GeoEntityTrackableLocation
from .entity import GeoEntityBaseCache, GeoEntityBaseTrackable


@dataclass(frozen=True, kw_only=True)
class GeocachingSensorEntityDescription(SensorEntityDescription):
    """Define Sensor entity description class."""

    value_fn: Callable[[GeocachingStatus], str | int | None]


PROFILE_SENSORS: tuple[GeocachingSensorEntityDescription, ...] = (
    GeocachingSensorEntityDescription(
        key="find_count",
        translation_key="find_count",
        native_unit_of_measurement="caches",
        value_fn=lambda status: status.user.find_count,
    ),
    GeocachingSensorEntityDescription(
        key="hide_count",
        translation_key="hide_count",
        native_unit_of_measurement="caches",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.hide_count,
    ),
    GeocachingSensorEntityDescription(
        key="favorite_points",
        translation_key="favorite_points",
        native_unit_of_measurement="points",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.favorite_points,
    ),
    GeocachingSensorEntityDescription(
        key="souvenir_count",
        translation_key="souvenir_count",
        native_unit_of_measurement="souvenirs",
        value_fn=lambda status: status.user.souvenir_count,
    ),
    GeocachingSensorEntityDescription(
        key="awarded_favorite_points",
        translation_key="awarded_favorite_points",
        native_unit_of_measurement="points",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.awarded_favorite_points,
    ),
    GeocachingSensorEntityDescription(
        key="nearby_caches",
        translation_key="nearby_caches",
        native_unit_of_measurement="caches",
        value_fn=lambda status: len(status.nearby_caches),
    ),
    GeocachingSensorEntityDescription(
        key="total_tracked_trackables_distance_traveled",
        translation_key="total_tracked_trackables_distance_traveled",
        native_unit_of_measurement="km",
        value_fn=lambda status: round(
            sum(
                [
                    trackable.kilometers_traveled or 0
                    for trackable in status.trackables.values()
                ]
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Geocaching sensor entry."""
    coordinator: GeocachingDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GeocachingProfileSensor(coordinator, description)
        for description in PROFILE_SENSORS
    )

    status: GeocachingStatus = await coordinator.fetch_new_status()
    entities: list[Entity] = []

    # Add entities for nearby caches
    for cache in status.nearby_caches:
        entities.extend(get_cache_entities(coordinator, cache, GeocacheCategory.NEARBY))

    # Add entities for tracked caches
    for cache in status.tracked_caches:
        entities.extend(
            get_cache_entities(coordinator, cache, GeocacheCategory.TRACKED)
        )

    # Add entities for tracked trackables
    for trackable in status.trackables.values():
        entities.extend(get_trackable_entities(coordinator, trackable))

    async_add_entities(entities)


class GeocachingProfileSensor(
    CoordinatorEntity[GeocachingDataUpdateCoordinator], SensorEntity
):
    """Representation of a Sensor."""

    entity_description: GeocachingSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        description: GeocachingSensorEntityDescription,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = GEOCACHING_ID_SENSOR_FORMAT.format(
            coordinator.data.user.reference_code, description.key
        )
        self._attr_device_info = DeviceInfo(
            name=f"Geocaching {coordinator.data.user.username}",
            identifiers={(DOMAIN, cast(str, coordinator.data.user.reference_code))},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Groundspeak, Inc.",
        )

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class GeoEntityTrackableSensorEntity(GeoEntityBaseTrackable, SensorEntity):
    """Representation of a trackable sensor."""

    entity_description: GeocachingTrackableEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        trackable: GeocachingTrackable,
        description: GeocachingTrackableEntityDescription,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, trackable, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime.date:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.trackable)


@dataclass(frozen=True, kw_only=True)
class GeocachingTrackableEntityDescription(SensorEntityDescription):
    """Define Sensor entity description class."""

    value_fn: Callable[[GeocachingTrackable], StateType | datetime.date]


TRACKABLE_SENSORS: tuple[GeocachingTrackableEntityDescription, ...] = (
    GeocachingTrackableEntityDescription(
        key="name",
        value_fn=lambda trackable: trackable.name,
    ),
    GeocachingTrackableEntityDescription(
        key="owner",
        value_fn=lambda trackable: trackable.owner.username,
    ),
    GeocachingTrackableEntityDescription(
        key="traveled_distance",
        native_unit_of_measurement="km",
        value_fn=lambda trackable: None
        if trackable.kilometers_traveled is None
        else round(trackable.kilometers_traveled),
    ),
    GeocachingTrackableEntityDescription(
        key="current_cache_code",
        value_fn=lambda trackable: trackable.current_geocache_code,
    ),
    GeocachingTrackableEntityDescription(
        key="current_cache_name",
        value_fn=lambda trackable: trackable.current_geocache_name,
    ),
    GeocachingTrackableEntityDescription(
        key="release_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda trackable: trackable.release_date,
    ),
)


def get_trackable_entities(
    coordinator: GeocachingDataUpdateCoordinator, trackable: GeocachingTrackable
) -> list[GeoEntityBaseTrackable]:
    """Generate all entities for a single trackable."""

    entities: list[GeoEntityBaseTrackable] = []

    # Tracker entities
    entities.extend([GeoEntityTrackableLocation(coordinator, trackable)])

    # Sensor entities
    entities.extend(
        [
            GeoEntityTrackableSensorEntity(coordinator, trackable, description)
            for description in TRACKABLE_SENSORS
        ]
    )

    return entities


class GeoEntityCacheSensorEntity(GeoEntityBaseCache, SensorEntity):
    """Representation of a cache sensor."""

    entity_description: GeocachingCacheSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        cache: GeocachingCache,
        description: GeocachingCacheSensorDescription,
        category: GeocacheCategory,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, cache, description.key, category)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime.date:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.cache)


@dataclass(frozen=True, kw_only=True)
class GeocachingCacheSensorDescription(SensorEntityDescription):
    """Define Sensor entity description class."""

    value_fn: Callable[[GeocachingCache], StateType | datetime.date]


CACHE_SENSORS: tuple[GeocachingCacheSensorDescription, ...] = (
    GeocachingCacheSensorDescription(
        key="name",
        value_fn=lambda cache: cache.name,
    ),
    GeocachingCacheSensorDescription(
        key="owner",
        value_fn=lambda cache: cache.owner.username,
    ),
    GeocachingCacheSensorDescription(
        key="found",
        value_fn=lambda cache: None
        if cache.found_by_user is None
        else "Yes"
        if cache.found_by_user is True
        else "No",
    ),
    GeocachingCacheSensorDescription(
        key="found_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda cache: cache.found_date_time,
    ),
    GeocachingCacheSensorDescription(
        key="favorite_points",
        native_unit_of_measurement="points",
        value_fn=lambda cache: cache.favorite_points,
    ),
    GeocachingCacheSensorDescription(
        key="hidden_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda cache: cache.hidden_date,
    ),
)


def get_cache_entities(
    coordinator: GeocachingDataUpdateCoordinator,
    cache: GeocachingCache,
    category: GeocacheCategory,
) -> list[GeoEntityBaseCache]:
    """Generate all entities for a single cache."""
    entities: list[GeoEntityBaseCache] = []

    # Tracker entities
    entities.extend([GeoEntityCacheLocation(coordinator, cache, category)])

    # Sensor entities
    entities.extend(
        [
            GeoEntityCacheSensorEntity(coordinator, cache, description, category)
            for description in CACHE_SENSORS
        ]
    )

    return entities
