"""Device tracker entities for Geocaching."""

from typing import Any

from geocachingapi.models import (
    GeocachingCache,
    GeocachingTrackable,
    GeocachingTrackableJourney,
)

from homeassistant.components.device_tracker.config_entry import TrackerEntity

from .const import GeocacheCategory
from .coordinator import GeocachingDataUpdateCoordinator
from .entity import GeoEntityBaseCache, GeoEntityBaseTrackable


# A tracker entity that allows us to show caches on a map.
class GeoEntityTrackableLocation(GeoEntityBaseTrackable, TrackerEntity):
    """Entity for a trackable GPS location."""

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        trackable: GeocachingTrackable,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, trackable, "location")

    @property
    def native_value(self) -> str | None:
        """Return the reference code of the trackable."""
        return self.trackable.reference_code

    @property
    def latitude(self) -> float:
        """Return the latitude of the trackable."""
        return float(self.trackable.coordinates.latitude or 0)

    @property
    def longitude(self) -> float:
        """Return the longitude of the trackable."""
        return float(self.trackable.coordinates.longitude or 0)

    @property
    def location_name(self) -> str | None:
        """Return the location of the cache."""
        # The location name is set to the reference code, so the code can be displayed as a label in the map using `label_mode: state`
        return self.trackable.reference_code

    def _format_travel_log_entry(
        self, journey: GeocachingTrackableJourney
    ) -> dict[str, Any]:
        """Format a single journey entry."""
        distance: str = (
            "Unknown"
            if journey.distance_km is None
            else f"{round(journey.distance_km)} km"
        )
        return {
            "date": journey.date,
            "username": journey.user.username,
            "location_name": journey.location_name,
            "distance_travelled": distance,
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the extra state attributes."""
        return {
            "URL": self.trackable.url,
            "travel_log": []
            if self.trackable.journeys is None
            else [
                self._format_travel_log_entry(journey)
                for journey in self.trackable.journeys
            ],
        }


# A tracker entity that allows us to show caches on a map.
class GeoEntityCacheLocation(GeoEntityBaseCache, TrackerEntity):
    """Entity for a cache GPS location."""

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        cache: GeocachingCache,
        category: GeocacheCategory,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, cache, "location", category)

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
        # The location name is set to the reference code, so the code can be displayed as a label in the map using `label_mode: state`
        return self.cache.reference_code

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the extra state attributes."""
        return {
            "URL": self.cache.url,
        }
