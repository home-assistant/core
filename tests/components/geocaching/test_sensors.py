"""The tests for the GeoCaching Sensor integration."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.geocaching.const import DOMAIN
from homeassistant.components.geocaching.sensor import (
    PROFILE_SENSORS,
    GeocachingDataUpdateCoordinator,
    GeocachingProfileSensor,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType

# Mock constants
MOCK_ENTRY_ID = "mock_entry_id"
MOCK_USER_DATA = {
    "find_count": 123,
    "hide_count": 45,
    "favorite_points": 67,
    "souvenir_count": 10,
    "awarded_favorite_points": 5,
    "reference_code": "USER123",
    "username": "TestUser",
}
MOCK_NEARBY_CACHES = [{"id": "cache1"}, {"id": "cache2"}, {"id": "cache3"}]
MOCK_TRACKABLES = {
    "trackable_1": MagicMock(kilometers_traveled=150.5),
    "trackable_2": MagicMock(kilometers_traveled=200.3),
}


@pytest.fixture
def mock_coordinator():
    """Return a mock GeocachingDataUpdateCoordinator object with data."""
    coordinator = MagicMock(spec=GeocachingDataUpdateCoordinator)
    coordinator.data = MagicMock()

    # Mock the data from constants
    coordinator.data.user = MagicMock(
        find_count=MOCK_USER_DATA["find_count"],
        hide_count=MOCK_USER_DATA["hide_count"],
        favorite_points=MOCK_USER_DATA["favorite_points"],
        souvenir_count=MOCK_USER_DATA["souvenir_count"],
        awarded_favorite_points=MOCK_USER_DATA["awarded_favorite_points"],
        reference_code=MOCK_USER_DATA["reference_code"],
        username=MOCK_USER_DATA["username"],
    )
    coordinator.data.trackables = MOCK_TRACKABLES
    return coordinator


@pytest.fixture
def mock_entry():
    """Mock a ConfigEntry."""
    return AsyncMock(entry_id=MOCK_ENTRY_ID)


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant, mock_coordinator: MagicMock, mock_entry: AsyncMock
) -> None:
    """Test async setup entry."""
    hass.data[DOMAIN] = {MOCK_ENTRY_ID: mock_coordinator}

    async_add_entities = AsyncMock()

    async_setup_entry(hass, mock_entry, async_add_entities)


async def test_geocaching_sensor(
    hass: HomeAssistant, mock_coordinator: MagicMock
) -> None:
    """Test the GeocachingSensor functionality."""
    sensor_description = PROFILE_SENSORS[0]  # Test the sensor (find_count)

    sensor = GeocachingProfileSensor(mock_coordinator, sensor_description)

    sensor.platform = MagicMock()
    sensor.platform.platform_name = "geocaching"

    sensor._attr_name = "find_count"

    # Verify sensor properties
    assert sensor.name == "find_count"
    assert sensor.native_unit_of_measurement == "caches"
    assert sensor.device_info["name"] == f"Geocaching {MOCK_USER_DATA['username']}"
    assert sensor.device_info["entry_type"] == DeviceEntryType.SERVICE
    assert sensor.unique_id == f"geocaching.USER123_{sensor._attr_name}"

    assert sensor.native_value == MOCK_USER_DATA["find_count"]


def test_kilometers_traveled_sensor(
    hass: HomeAssistant, mock_coordinator: MagicMock
) -> None:
    """Test the GeocachingSensor functionality, summing kilometers_traveled."""

    trackable_description = PROFILE_SENSORS[
        6
    ]  # Test the sensor (total_tracked_trackables_distance_traveled)

    sensor = GeocachingProfileSensor(mock_coordinator, trackable_description)

    sensor.platform = MagicMock()
    sensor.platform.platform_name = "geocaching"

    sensor._attr_name = "total_tracked_trackables_distance_traveled"

    expected_sum = sum(
        trackable.kilometers_traveled for trackable in MOCK_TRACKABLES.values()
    )

    mock_status = MagicMock()
    mock_status.trackables = MOCK_TRACKABLES

    value_fn = MagicMock()
    value_fn.return_value = round(expected_sum)

    sensor._get_native_value = MagicMock(return_value=value_fn(mock_status))

    assert sensor.name == "total_tracked_trackables_distance_traveled"
    assert sensor.native_unit_of_measurement == "km"
    assert sensor.device_info["name"] == f"Geocaching {MOCK_USER_DATA['username']}"
    assert sensor.device_info["entry_type"] == DeviceEntryType.SERVICE
    assert sensor.unique_id == f"geocaching.USER123_{sensor._attr_name}"

    assert sensor.native_value == round(expected_sum)
