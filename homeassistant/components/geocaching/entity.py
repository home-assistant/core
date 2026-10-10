"""Sensor entities for Geocaching."""

from typing import cast, override

from geocachingapi.models import GeocachingCache, GeocachingTrackable

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GeocachingDataUpdateCoordinator


# Base class for all platforms
class GeocachingBaseEntity(CoordinatorEntity[GeocachingDataUpdateCoordinator]):
    """Base class for Geocaching sensors."""

    _attr_has_entity_name = True


# Base class for cache entities
class GeocachingCacheEntity(GeocachingBaseEntity):
    """Base class for Geocaching cache entities."""

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        cache: GeocachingCache,
        reference_code: str,
    ) -> None:
        """Initialize the Geocaching cache entity."""
        super().__init__(coordinator)

        self._reference_code = reference_code.strip().upper()

        # A device can have multiple entities, and for a cache
        # which requires multiple entities we want to group them
        # together. Therefore, we create a device for each cache,
        # which holds all related entities.
        self._attr_device_info = DeviceInfo(
            name=f"Geocache {cache.name}",
            identifiers={(DOMAIN, self._reference_code)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=cache.owner.username,
        )

    @property
    def cache(self) -> GeocachingCache:
        """Return the latest cache data."""
        return self.coordinator.data.tracked_caches[self._reference_code]

    @property
    @override
    def available(self) -> bool:
        """Return whether the cache is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._reference_code in self.coordinator.data.tracked_caches
        )


class GeocachingTrackableEntity(GeocachingBaseEntity):
    """Base class for Geocaching trackable entities."""

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        trackable: GeocachingTrackable,
    ) -> None:
        """Initialize the Geocaching trackable entity."""
        super().__init__(coordinator)

        self._reference_code = cast(str, trackable.reference_code).strip().upper()
        account_reference_code = cast(str, coordinator.data.user.reference_code)

        self._attr_device_info = DeviceInfo(
            name=f"Trackable {trackable.name}",
            identifiers={(DOMAIN, f"{account_reference_code}_{self._reference_code}")},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Groundspeak, Inc.",
        )

    @property
    def trackable(self) -> GeocachingTrackable:
        """Return the latest trackable data."""
        return self.coordinator.data.trackables[self._reference_code]

    @property
    @override
    def available(self) -> bool:
        """Return whether the trackable is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._reference_code in self.coordinator.data.trackables
        )
