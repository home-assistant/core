"""Base entities for Geocaching devices."""

from typing import cast

from geocachingapi.models import GeocachingCache

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CACHE_ID_SENSOR_FORMAT, DOMAIN
from .coordinator import GeocachingDataUpdateCoordinator


# A device can have multiple entities, and for a cache which requires multiple entities we want to group them together.
# Therefore, we create a device for each cache, which holds all related entities.
# This function returns the device info for a cache.
def get_cache_device_info(cache: GeocachingCache) -> DeviceInfo:
    """Generate device info for a cache."""
    return DeviceInfo(
        name=f"Geocache {cache.reference_code}",
        identifiers={(DOMAIN, cast(str, cache.reference_code))},
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
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator)
        self.cache = cache

        # Set the device info from the cache, to group all entities for a cache together
        self._attr_device_info = get_cache_device_info(cache)

        self._attr_unique_id = CACHE_ID_SENSOR_FORMAT.format(
            cache.reference_code, entity_type
        )

        # The translation key determines the name of the entity as this is the lookup for the `strings.json` file.
        self._attr_translation_key = f"cache_{entity_type}"
