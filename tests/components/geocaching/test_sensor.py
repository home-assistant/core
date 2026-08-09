"""Test the Geocaching sensor platform."""

from unittest.mock import MagicMock

from geocachingapi.models import GeocachingCache, GeocachingStatus, GeocachingTrackable

from homeassistant.components.geocaching.sensor import (
    CACHE_SENSORS,
    TRACKABLE_SENSORS,
    GeoEntityCacheSensorEntity,
    GeoEntityTrackableSensorEntity,
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


def test_trackable_sensor_uses_latest_coordinator_data() -> None:
    """Test that a trackable sensor uses the latest coordinator data."""
    owner = MagicMock()
    owner.username = "TrackableOwner"

    first_trackable = GeocachingTrackable(
        reference_code="TB12345",
        name="Test trackable",
        owner=owner,
        kilometers_traveled=10.5,
    )

    first_status = GeocachingStatus()
    first_status.tracked_trackables = [first_trackable]

    coordinator = MagicMock()
    coordinator.data = first_status

    description = next(
        description
        for description in TRACKABLE_SENSORS
        if description.key == "kilometers_traveled"
    )

    entity = GeoEntityTrackableSensorEntity(
        coordinator,
        first_trackable,
        description,
    )

    assert entity.native_value == 10.5

    updated_trackable = GeocachingTrackable(
        reference_code="TB12345",
        name="Test trackable",
        owner=owner,
        kilometers_traveled=20.5,
    )

    updated_status = GeocachingStatus()
    updated_status.tracked_trackables = [updated_trackable]

    coordinator.data = updated_status

    assert entity.native_value == 20.5
