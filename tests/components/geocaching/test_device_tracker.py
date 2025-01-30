"""The tests for the GeoCaching device tracker integration."""

from datetime import datetime
from unittest.mock import MagicMock

from geocachingapi.models import GeocachingTrackable, GeocachingTrackableJourney
import pytest

from homeassistant.components.geocaching.device_tracker import (
    GeocacheCategory,
    GeocachingCache,
    GeocachingDataUpdateCoordinator,
    GeoEntityCacheLocation,
    GeoEntityTrackableLocation,
)


@pytest.fixture
def mock_trackable():
    """Return a mocked GeocachingTrackable object."""
    trackable = MagicMock(spec=GeocachingTrackable)
    trackable.reference_code = "T12345"
    trackable.coordinates.latitude = 50.0
    trackable.coordinates.longitude = 8.0
    trackable.url = "http://example.com/trackable"

    data = {
        "loggedDate": "2021-01-01",
        "owner": {"username": "User1"},
    }

    # Pass the dictionary to the constructor
    journey = GeocachingTrackableJourney(data=data)

    trackable.journeys = [journey]
    return trackable


@pytest.fixture
def mock_cache():
    """Return a mock GeocachingCache object."""
    cache = MagicMock(spec=GeocachingCache)
    cache.reference_code = "C67890"
    cache.coordinates = MagicMock()
    cache.coordinates.latitude = 51.0  # Set valid latitude
    cache.coordinates.longitude = 9.0  # Set valid longitude
    cache.url = "http://example.com/cache"  # Set a valid URL
    return cache


@pytest.fixture
def mock_coordinator():
    """Return a mock GeocachingDataUpdateCoordinator object."""
    return MagicMock(spec=GeocachingDataUpdateCoordinator)


@pytest.fixture
def mock_category():
    """Return a mock GeocacheCategory object."""
    category = MagicMock(spec=GeocacheCategory)
    category.value = "category_value"  # Mock the 'value' attribute
    return category


def test_geo_entity_trackable_location(mock_trackable, mock_coordinator) -> None:
    """Test the GeoEntityTrackableLocation class."""
    entity = GeoEntityTrackableLocation(mock_coordinator, mock_trackable)

    # Test basic properties
    assert entity.native_value == "T12345"
    assert entity.latitude == 50.0
    assert entity.longitude == 8.0
    assert entity.location_name == "T12345"

    # Test extra state attributes
    attributes = entity.extra_state_attributes
    assert attributes["URL"] == "http://example.com/trackable"
    assert len(attributes["travel_log"]) == 1
    assert attributes["travel_log"][0] == {
        "date": datetime(2021, 1, 1).date(),
        "username": "User1",
        "location_name": None,
        "distance_travelled": "Unknown",
    }


def test_geo_entity_cache_location(mock_cache, mock_coordinator, mock_category) -> None:
    """Test the GeoEntityCacheLocation class."""
    entity = GeoEntityCacheLocation(mock_coordinator, mock_cache, mock_category)

    # Test basic properties
    assert entity.native_value == "C67890"
    assert entity.latitude == 51.0
    assert entity.longitude == 9.0
    assert entity.location_name == "C67890"

    # Test extra state attributes
    attributes = entity.extra_state_attributes
    assert attributes["URL"] == "http://example.com/cache"
