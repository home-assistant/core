"""Entities for Geocaching devices."""

import datetime
from typing import cast

from geocachingapi.models import GeocachingCache

from homeassistant.components.date import DateEntity
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NEARBY_CACHE_ID_SENSOR_FORMAT
from .coordinator import GeocachingDataUpdateCoordinator


def get_cache_entities(
    coordinator: GeocachingDataUpdateCoordinator, cache: GeocachingCache
) -> list[Entity]:
    """Generate all entities for a single cache."""
    return [
        GeoEntity_Cache_Location(coordinator, cache),
        GeoEntity_Cache_HideDate(coordinator, cache),
    ]


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
class GeoEntity_Cache_Location(
    CoordinatorEntity[GeocachingDataUpdateCoordinator], TrackerEntity
):
    """Representation of a Sensor."""

    _attr_has_entity_name = True
    cache: GeocachingCache

    def __init__(
        self, coordinator: GeocachingDataUpdateCoordinator, cache: GeocachingCache
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator)
        self.cache = cache
        self._attr_unique_id = NEARBY_CACHE_ID_SENSOR_FORMAT.format(
            cache.reference_code, "location"
        )
        self._attr_device_info = get_cache_device_info(coordinator, cache)  # type: ignore[assignment]

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.cache.reference_code

    @property
    def latitude(self) -> float:
        """Return the latitude of the sensor."""
        return float(self.cache.coordinates.latitude or 0)

    @property
    def longitude(self) -> float:
        """Return the longitude of the sensor."""
        return float(self.cache.coordinates.longitude or 0)

    @property
    def location_name(self) -> str | None:
        """Return the name of the location."""
        return self.cache.reference_code


# pylint: disable=hass-enforce-class-module
class GeoEntity_Cache_HideDate(
    CoordinatorEntity[GeocachingDataUpdateCoordinator], DateEntity
):
    """Representation of a Sensor."""

    _attr_has_entity_name = True
    cache: GeocachingCache

    def __init__(
        self, coordinator: GeocachingDataUpdateCoordinator, cache: GeocachingCache
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator)
        self.cache = cache
        self._attr_unique_id = NEARBY_CACHE_ID_SENSOR_FORMAT.format(
            cache.reference_code, "hide_date"
        )
        self._attr_device_info = get_cache_device_info(coordinator, cache)

    @property
    def native_value(self) -> datetime.date | None:
        """Return the state of the sensor."""
        return datetime.date(2022, 3, 13)
