"""Test the Geocaching sensor platform."""

from unittest.mock import MagicMock

from geocachingapi.models import GeocachingCache, GeocachingStatus

from homeassistant.components.geocaching.sensor import (
    CACHE_SENSORS,
    GeoEntityCacheSensorEntity,
)


def test_cache_sensor_uses_latest_coordinator_data() -> None:
    """Test that a cache sensor uses the latest coordinator data."""
    owner = MagicMock()
    owner.username = "CacheOwner"

    first_cache = GeocachingCache(
        reference_code="GC12345",
        name="Test cache",
        owner=owner,
        favorite_points=10,
    )

    first_status = GeocachingStatus()
    first_status.tracked_caches = [first_cache]

    coordinator = MagicMock()
    coordinator.data = first_status

    description = next(
        description
        for description in CACHE_SENSORS
        if description.key == "favorite_points"
    )

    entity = GeoEntityCacheSensorEntity(
        coordinator,
        first_cache,
        description,
    )

    assert entity.native_value == 10

    updated_cache = GeocachingCache(
        reference_code="GC12345",
        name="Test cache",
        owner=owner,
        favorite_points=20,
    )

    updated_status = GeocachingStatus()
    updated_status.tracked_caches = [updated_cache]

    coordinator.data = updated_status

    assert entity.native_value == 20
