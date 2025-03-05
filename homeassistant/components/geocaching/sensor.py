"""Platform for sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
from typing import cast

from geocachingapi.models import GeocachingStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PROFILE_ID_SENSOR_FORMAT
from .coordinator import GeocachingDataUpdateCoordinator
from .entity import GeocachingCache, GeoEntityBaseCache


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
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Geocaching sensor entry."""
    coordinator: GeocachingDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GeocachingProfileSensor(coordinator, description)
        for description in PROFILE_SENSORS
    )

    status: GeocachingStatus = await coordinator.fetch_new_status()
    entities: list[Entity] = []

    # Add entities for tracked caches
    for cache in status.tracked_caches:
        entities.extend(get_cache_entities(coordinator, cache))

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
        self._attr_unique_id = PROFILE_ID_SENSOR_FORMAT.format(
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
) -> list[GeoEntityBaseCache]:
    """Generate all entities for a single cache."""
    entities: list[GeoEntityBaseCache] = []

    # Sensor entities
    entities.extend(
        [
            GeoEntityCacheSensorEntity(coordinator, cache, description)
            for description in CACHE_SENSORS
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
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, cache, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime.date:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.cache)
