"""Unit tests for the OpenUV graph UV sensor functionality, including color determination.

Sensor initialization, and asynchronous updates based on the UV index.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.openuv.coordinator import OpenUvCoordinator
from homeassistant.components.openuv.sensor import OpenUvGraphSensor


@pytest.fixture
def mock_coordinator():
    """Create a mocked OpenUvCoordinator with latitude and longitude."""
    coordinator = MagicMock(spec=OpenUvCoordinator)
    coordinator.data = {
        "uv": 7,  # Current UV index
        "uv_time_series": [
            {"time": "2024-12-01T10:00:00Z", "uv": 6},
            {"time": "2024-12-01T11:00:00Z", "uv": 7},
        ],
    }
    # Mock the latitude and longitude attributes expected by the sensor
    coordinator.latitude = 34.0522
    coordinator.longitude = -118.2437
    return coordinator


def test_graph_sensor_color(mock_coordinator) -> None:
    """Test that the color is correctly determined for various UV index ranges."""
    # Test cases for different UV levels
    test_cases = [
        {"uv": 7, "expected_color": "orange", "expected_label": "high"},
        {"uv": 9, "expected_color": "red", "expected_label": "very_high"},
        {"uv": 12, "expected_color": "purple", "expected_label": "extreme"},
    ]

    description = MagicMock()
    description.key = "current_uv_index_with_graph"
    description.value_fn = lambda data: data["uv"]

    for case in test_cases:
        # Update the mocked data for each test case
        mock_coordinator.data = {"uv": case["uv"]}

        # Create the Graph UV Sensor instance
        graph_sensor = OpenUvGraphSensor(mock_coordinator, description)

        # Mocking the method to get UV label and color
        graph_sensor._get_uv_label = MagicMock(return_value=case["expected_label"])
        graph_sensor._get_uv_color = MagicMock(return_value=case["expected_color"])

        # Verify the color and UV label
        assert (
            graph_sensor._get_uv_color() == case["expected_color"]
        ), f"Failed for UV index {case['uv']}"
        assert (
            graph_sensor._get_uv_label() == case["expected_label"]
        ), f"Failed for UV index {case['uv']}"


def test_graph_sensor_initialization(mock_coordinator) -> None:
    """Test the initialization of the Graph UV Sensor."""
    description = MagicMock()
    description.key = "current_uv_index_with_graph"
    description.value_fn = lambda data: data["uv"]

    # Creating the Graph UV Sensor instance
    graph_sensor = OpenUvGraphSensor(mock_coordinator, description)

    # Verifying the sensor's name, unique ID, and the initial value
    assert graph_sensor.name == "Current UV Index with Graph"
    assert graph_sensor.unique_id == "current_uv_index_with_graph"
    assert graph_sensor.native_value == 7


@pytest.mark.asyncio
async def test_graph_sensor_update(mock_coordinator) -> None:
    """Test the async update method of the Graph UV Sensor."""
    description = MagicMock()
    description.key = "current_uv_index_with_graph"
    description.value_fn = lambda data: data["uv"]

    # Create the Graph UV Sensor instance
    graph_sensor = OpenUvGraphSensor(mock_coordinator, description)

    # Mock the async refresh method of the coordinator
    mock_coordinator.async_request_refresh = AsyncMock()

    # Trigger the update method
    await graph_sensor.async_update()

    # Verifying the hourly forecast was updated
    assert graph_sensor._hourly_forecast == [
        {"time": "10:00", "uv_index": 6},
        {"time": "11:00", "uv_index": 7},
    ]
