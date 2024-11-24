"""Entities for Geocaching devices."""

from collections.abc import Callable
from dataclasses import dataclass
import datetime
from typing import cast

from geocachingapi.models import GeocachingCache

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NEARBY_CACHE_ID_SENSOR_FORMAT
from .coordinator import GeocachingDataUpdateCoordinator


# A device can have multiple entities, and for a cache which requires multiple entities we want to group them together.
# Therefore, we create a device for each cache, which holds all related entities.
# This function returns the device info for a cache.
def get_cache_device_info(
    coordinator: GeocachingDataUpdateCoordinator, cache: GeocachingCache
) -> DeviceInfo:
    """Generate device info for a cache."""
    return DeviceInfo(
        name=f"Geocaching {coordinator.data.user.username}",
        identifiers={(DOMAIN, cast(str, cache.reference_code))},
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="Groundspeak, Inc.",
    )


# pylint: disable=hass-enforce-class-module
# Base class for a cache entity.
# Sets the device, ID and translation settings to correctly group the entity to the correct cache device and give it the correct name.
class GeoEntity_BaseCache(CoordinatorEntity[GeocachingDataUpdateCoordinator], Entity):
    """Base class for Geocaching entities."""

    _attr_has_entity_name = True
    cache: GeocachingCache

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        cache: GeocachingCache,
        entity_type: str,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator)
        self.cache = cache

        # Set the device info from the cache, to group all entities for a cache together
        self._attr_device_info = get_cache_device_info(coordinator, cache)

        # TODO: Change this from NEARBY_CACHE... | pylint: disable=fixme
        self._attr_unique_id = NEARBY_CACHE_ID_SENSOR_FORMAT.format(
            cache.reference_code, entity_type
        )

        # The translation key determines the name of the entity as this is the lookup for the `strings.json` file.
        self._attr_translation_key = f"cache_{entity_type}"

        # For a cache, the reference code (unique ID for the cache) needs to be included in the name to avoid duplicates.
        # Therefore, we interpolate the reference code into the name using translation placeholders.
        self._attr_translation_placeholders = {
            "reference_code": cache.reference_code or ""
        }


# pylint: disable=hass-enforce-class-module
# A tracker entity that allows us to show caches on a map.
class GeoEntity_Cache_Location(GeoEntity_BaseCache, TrackerEntity):
    """Entity for a cache GPS location."""

    def __init__(
        self, coordinator: GeocachingDataUpdateCoordinator, cache: GeocachingCache
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, cache, "location")

    @property
    def native_value(self) -> str | None:
        """Return the reference code of the cache."""
        return self.cache.reference_code

    @property
    def latitude(self) -> float:
        """Return the latitude of the cache."""
        return float(self.cache.coordinates.latitude or 0)

    @property
    def longitude(self) -> float:
        """Return the longitude of the cache."""
        return float(self.cache.coordinates.longitude or 0)

    @property
    def location_name(self) -> str | None:
        """Return the location of the cache."""
        return "Sweden"  # TODO: Connect with API, either cache country or state if it works for all countries | pylint: disable=fixme


@dataclass(frozen=True, kw_only=True)
class GeocachingCacheEntityDescription(SensorEntityDescription):
    """Define Sensor entity description class."""

    value_fn: Callable[[GeocachingCache], StateType | datetime.date]


SENSORS: tuple[GeocachingCacheEntityDescription, ...] = (
    GeocachingCacheEntityDescription(
        key="find_count",
        native_unit_of_measurement="caches",
        value_fn=lambda cache: 3,  # TODO: Connect with API | pylint: disable=fixme
    ),
    GeocachingCacheEntityDescription(
        key="favorite_points",
        native_unit_of_measurement="points",
        value_fn=lambda cache: 15,  # TODO: Connect with API | pylint: disable=fixme
    ),
    GeocachingCacheEntityDescription(
        key="hide_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda cache: datetime.date(
            2022, 3, 13
        ),  # TODO: Connect with API | pylint: disable=fixme
    ),
)


# pylint: disable=hass-enforce-class-module
class GeoEntity_Cache_SensorEntity(GeoEntity_BaseCache, SensorEntity):
    """Representation of a cache sensor."""

    entity_description: GeocachingCacheEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        cache: GeocachingCache,
        description: GeocachingCacheEntityDescription,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, cache, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime.date:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.cache)


def get_cache_entities(
    coordinator: GeocachingDataUpdateCoordinator, cache: GeocachingCache
) -> list[GeoEntity_BaseCache]:
    """Generate all entities for a single cache."""
    entities: list[GeoEntity_BaseCache] = []

    # Tracker entities
    entities.extend([GeoEntity_Cache_Location(coordinator, cache)])

    # Sensor entities
    entities.extend(
        [
            GeoEntity_Cache_SensorEntity(coordinator, cache, description)
            for description in SENSORS
        ]
    )
    return entities
