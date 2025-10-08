"""Platform for sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
from typing import cast

from geocachingapi.models import GeocachingCache, GeocachingStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import GeocachingConfigEntry, GeocachingDataUpdateCoordinator
from .entity import GeocachingBaseEntity, GeocachingCacheEntity


@dataclass(frozen=True, kw_only=True)
class GeocachingSensorEntityDescription(SensorEntityDescription):
    """Define Sensor entity description class."""

    value_fn: Callable[[GeocachingStatus], str | int | None]


PROFILE_SENSORS: tuple[GeocachingSensorEntityDescription, ...] = (
    GeocachingSensorEntityDescription(
        key="find_count",
        translation_key="find_count",
        value_fn=lambda status: status.user.find_count,
    ),
    GeocachingSensorEntityDescription(
        key="hide_count",
        translation_key="hide_count",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.hide_count,
    ),
    GeocachingSensorEntityDescription(
        key="favorite_points",
        translation_key="favorite_points",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.favorite_points,
    ),
    GeocachingSensorEntityDescription(
        key="souvenir_count",
        translation_key="souvenir_count",
        value_fn=lambda status: status.user.souvenir_count,
    ),
    GeocachingSensorEntityDescription(
        key="awarded_favorite_points",
        translation_key="awarded_favorite_points",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.awarded_favorite_points,
    ),
)


@dataclass(frozen=True, kw_only=True)
class GeocachingCacheSensorDescription(SensorEntityDescription):
    """Define Sensor entity description class."""

    value_fn: Callable[[GeocachingCache], StateType | datetime.date]


CACHE_SENSORS: tuple[GeocachingCacheSensorDescription, ...] = (
    GeocachingCacheSensorDescription(
        key="found_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda cache: cache.found_date_time,
    ),
    GeocachingCacheSensorDescription(
        key="favorite_points",
        value_fn=lambda cache: cache.favorite_points,
    ),
    GeocachingCacheSensorDescription(
        key="hidden_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda cache: cache.hidden_date,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeocachingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Geocaching sensor entry."""
    coordinator = entry.runtime_data

    entities: list[Entity] = []

    entities.extend(
        GeocachingProfileSensor(coordinator, description)
        for description in PROFILE_SENSORS
    )

    status = coordinator.data

    # Add entities for tracked caches
    entities.extend(
        GeoEntityCacheSensorEntity(coordinator, cache, description)
        for cache in status.tracked_caches
        for description in CACHE_SENSORS
    )

    async_add_entities(entities)


# Base class for a cache entity.
# Sets the device, ID and translation settings to correctly group the entity to the correct cache device and give it the correct name.
class GeoEntityBaseCache(GeocachingCacheEntity, SensorEntity):
    """Base class for cache entities."""

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        cache: GeocachingCache,
        key: str,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, cache)

        self._attr_unique_id = f"{cache.reference_code}_{key}"

        # The translation key determines the name of the entity as this is the lookup for the `strings.json` file.
        self._attr_translation_key = f"cache_{key}"


class GeoEntityCacheSensorEntity(GeoEntityBaseCache, SensorEntity):
    """Representation of a cache sensor."""

    entity_description: GeocachingCacheSensorDescription

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


class GeocachingProfileSensor(GeocachingBaseEntity, SensorEntity):
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
        self._attr_unique_id = (
            f"{coordinator.data.user.reference_code}_{description.key}"
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
