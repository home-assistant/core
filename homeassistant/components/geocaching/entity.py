"""Base entities for Geocaching devices."""

from typing import cast

from geocachingapi.models import GeocachingCache, GeocachingTrackable

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CACHE_ID_SENSOR_FORMAT,
    DOMAIN,
    TRACKABLE_ID_SENSOR_FORMAT,
    GeocacheCategory,
)
from .coordinator import GeocachingDataUpdateCoordinator


# A device can have multiple entities, and for a cache which requires multiple entities we want to group them together.
# Therefore, we create a device for each cache, which holds all related entities.
# This function returns the device info for a cache.
def get_cache_device_info(
    cache: GeocachingCache, category: GeocacheCategory
) -> DeviceInfo:
    """Generate device info for a cache."""
    return DeviceInfo(
        name=f"Geocache {category.value} {cache.reference_code}",
        identifiers={(DOMAIN, cast(str, cache.reference_code))},
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="Groundspeak, Inc.",
    )


# A device can have multiple entities, and for a trackable which requires multiple entities we want to group them together.
# Therefore, we create a device for each trackable, which holds all related entities.
# This function returns the device info for a trackable.
def get_trackable_device_info(trackable: GeocachingTrackable) -> DeviceInfo:
    """Generate device info for a cache."""
    return DeviceInfo(
        name=f"Geotrackable {trackable.reference_code}",
        identifiers={(DOMAIN, cast(str, trackable.reference_code))},
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="Groundspeak, Inc.",
    )


# Base class for a cache entity.
# Sets the device, ID and translation settings to correctly group the entity to the correct cache device and give it the correct name.
class GeoEntityBaseCache(CoordinatorEntity[GeocachingDataUpdateCoordinator], Entity):
    """Base class for cache entities."""

    _attr_has_entity_name = True
    cache: GeocachingCache

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        cache: GeocachingCache,
        entity_type: str,
        category: GeocacheCategory,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator)
        self.cache = cache

        # Set the device info from the cache, to group all entities for a cache together
        self._attr_device_info = get_cache_device_info(cache, category)

        self._attr_unique_id = CACHE_ID_SENSOR_FORMAT.format(
            category.value, cache.reference_code, entity_type
        )

        # The translation key determines the name of the entity as this is the lookup for the `strings.json` file.
        self._attr_translation_key = f"cache_{entity_type}"


# Base class for a trackable entity.
# Sets the device, ID and translation settings to correctly group the entity to the correct trackable device and give it the correct name.
class GeoEntityBaseTrackable(
    CoordinatorEntity[GeocachingDataUpdateCoordinator], Entity
):
    """Base class for trackable entities."""

    _attr_has_entity_name = True
    trackable: GeocachingTrackable

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        trackable: GeocachingTrackable,
        entity_type: str,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator)
        self.trackable = trackable

        # Set the device info from the trackable, to group all entities for a trackable together
        self._attr_device_info = get_trackable_device_info(trackable)

        self._attr_unique_id = TRACKABLE_ID_SENSOR_FORMAT.format(
            trackable.reference_code, entity_type
        )

        # The translation key determines the name of the entity as this is the lookup for the `strings.json` file.
        self._attr_translation_key = f"trackable_{entity_type}"
