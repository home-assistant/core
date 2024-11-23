"""Entities for Geocaching devices."""

import datetime
from typing import cast

from geocachingapi.models import GeocachingCache

from homeassistant.components.date import DateEntity
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NEARBY_CACHE_ID_SENSOR_FORMAT
from .coordinator import GeocachingDataUpdateCoordinator


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
class GeoEntity_Base(CoordinatorEntity[GeocachingDataUpdateCoordinator], Entity):
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
        self._attr_device_info = get_cache_device_info(coordinator, cache)
        # TODO: Change this from NEARBY_CACHE... | pylint: disable=fixme
        self._attr_unique_id = NEARBY_CACHE_ID_SENSOR_FORMAT.format(
            cache.reference_code, entity_type
        )


# pylint: disable=hass-enforce-class-module
class GeoEntity_Cache_Location(GeoEntity_Base, TrackerEntity):
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


# pylint: disable=hass-enforce-class-module
class GeoEntity_Cache_HideDate(GeoEntity_Base, DateEntity):
    """Entity for when a cache was hidden."""

    def __init__(
        self, coordinator: GeocachingDataUpdateCoordinator, cache: GeocachingCache
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, cache, "hide_date")

    @property
    def native_value(self) -> datetime.date | None:
        """Return hide date of the cache."""
        return datetime.date(
            2022, 3, 13
        )  # TODO: Connect with API | pylint: disable=fixme


class GeoEntity_Cache_IntegerBase(GeoEntity_Base, NumberEntity):
    """Base class for integer-based cache entities."""

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        cache: GeocachingCache,
        entity_type: str,
        unit: str,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, cache, entity_type)
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = unit


# pylint: disable=hass-enforce-class-module
class GeoEntity_Cache_NumberOfFinds(GeoEntity_Cache_IntegerBase, NumberEntity):
    """Entity for how many times a cache has been found."""

    def __init__(
        self, coordinator: GeocachingDataUpdateCoordinator, cache: GeocachingCache
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, cache, "find_count", "finds")

    @property
    def native_value(self) -> int | None:
        """Return the number of finds for the cache."""
        return 3  # TODO: Connect with API | pylint: disable=fixme


# pylint: disable=hass-enforce-class-module
class GeoEntity_Cache_NumberOfFavorites(GeoEntity_Cache_IntegerBase, NumberEntity):
    """Entity for how many favorites a cache has."""

    def __init__(
        self, coordinator: GeocachingDataUpdateCoordinator, cache: GeocachingCache
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, cache, "favorite_count", "favorites")

    @property
    def native_value(self) -> int | None:
        """Return the number of favorites for the cache."""
        return 12  # TODO: Connect with API | pylint: disable=fixme


def get_cache_entities(
    coordinator: GeocachingDataUpdateCoordinator, cache: GeocachingCache
) -> list[GeoEntity_Base]:
    """Generate all entities for a single cache."""
    return [
        GeoEntity_Cache_Location(coordinator, cache),
        GeoEntity_Cache_HideDate(coordinator, cache),
        GeoEntity_Cache_NumberOfFinds(coordinator, cache),
        GeoEntity_Cache_NumberOfFavorites(coordinator, cache),
    ]
