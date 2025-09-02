"""Test the Nederlandse Spoorwegen sensor platform."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.nederlandse_spoorwegen.const import DOMAIN
from homeassistant.components.nederlandse_spoorwegen.coordinator import (
    NSDataUpdateCoordinator,
)
from homeassistant.components.nederlandse_spoorwegen.sensor import (
    NSCoordinatorSensor,
    async_setup_entry,
    async_setup_platform,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class MockTrip:
    """Mock trip object."""

    def __init__(
        self,
        going=True,
        departure_time_planned=None,
        departure_time_actual=None,
        departure_platform_planned=None,
        departure_platform_actual=None,
        status=None,
    ) -> None:
        """Initialize mock trip."""
        self.going = going
        self.departure_time_planned = departure_time_planned
        self.departure_time_actual = departure_time_actual
        self.departure_platform_planned = departure_platform_planned
        self.departure_platform_actual = departure_platform_actual
        self.status = status


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "test_key",
            "routes": [
                {
                    "name": "Test Route",
                    "from": "RTD",
                    "to": "ASD",
                    "via": None,
                }
            ],
        },
    )


@pytest.fixture
def mock_coordinator():
    """Return a mock coordinator."""
    coordinator = Mock(spec=NSDataUpdateCoordinator)
    coordinator.data = None
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


async def test_async_setup_entry_no_initial_data(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test setup entry when coordinator has no initial data."""
    mock_coordinator = Mock(spec=NSDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.async_request_refresh = AsyncMock()

    mock_config_entry.runtime_data = mock_coordinator

    async_add_entities = Mock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should refresh to get initial data
    mock_coordinator.async_request_refresh.assert_called_once()
    # Should add no entities initially when no data is available
    async_add_entities.assert_called_once_with([])


async def test_async_setup_entry_with_routes(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test setup entry with route data."""
    mock_coordinator = Mock(spec=NSDataUpdateCoordinator)
    mock_coordinator.data = {
        "routes": {
            "test_route_1": {
                "route": {CONF_NAME: "Test Route 1"},
                "next_trip": MockTrip(),
            },
            "test_route_2": {
                "route": {CONF_NAME: "Test Route 2"},
                "next_trip": MockTrip(),
            },
        }
    }

    mock_config_entry.runtime_data = mock_coordinator

    async_add_entities = Mock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should not refresh as we have data
    mock_coordinator.async_request_refresh.assert_not_called()

    # Should add two sensor entities
    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 2
    assert all(isinstance(entity, NSCoordinatorSensor) for entity in entities)


class TestNSCoordinatorSensor:
    """Test NSCoordinatorSensor class."""

    def test_init(self, mock_coordinator):
        """Test sensor initialization."""
        route = {CONF_NAME: "Test Route"}
        route_key = "test_route"

        sensor = NSCoordinatorSensor(
            coordinator=mock_coordinator,
            route_key=route_key,
            route=route,
        )

        assert sensor._route_key == route_key
        assert sensor._route == route
        assert sensor._attr_name == "Test Route"
        assert sensor._attr_unique_id == f"{DOMAIN}_test_route"
        assert sensor._attr_attribution == "Data provided by NS"
        assert sensor._attr_icon == "mdi:train"
        assert sensor._attr_has_entity_name is True

    def test_native_value_no_coordinator_data(self, mock_coordinator):
        """Test native_value when coordinator has no data."""
        mock_coordinator.data = None
        route = {CONF_NAME: "Test Route"}
        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route)

        assert sensor.native_value is None

    def test_native_value_no_routes(self, mock_coordinator):
        """Test native_value when coordinator data has no routes."""
        mock_coordinator.data = {"other_data": "value"}
        route = {CONF_NAME: "Test Route"}
        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route)

        assert sensor.native_value is None

    def test_native_value_no_route_data(self, mock_coordinator):
        """Test native_value when specific route has no data."""
        mock_coordinator.data = {"routes": {"other_route": {}}}
        route = {CONF_NAME: "Test Route"}
        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route)

        assert sensor.native_value is None

    def test_native_value_no_next_trip(self, mock_coordinator):
        """Test native_value when route has no next trip."""
        mock_coordinator.data = {
            "routes": {"test_route": {"route": {}, "next_trip": None}}
        }
        route = {CONF_NAME: "Test Route"}
        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route)

        assert sensor.native_value is None

    def test_native_value_with_actual_time(self, mock_coordinator):
        """Test native_value returns actual departure time when available."""
        departure_actual = datetime(2023, 12, 25, 14, 30)
        departure_planned = datetime(2023, 12, 25, 14, 25)

        trip = MockTrip(
            departure_time_actual=departure_actual,
            departure_time_planned=departure_planned,
        )

        mock_coordinator.data = {
            "routes": {"test_route": {"route": {}, "next_trip": trip}}
        }
        route = {CONF_NAME: "Test Route"}
        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route)

        assert sensor.native_value == "14:30"

    def test_native_value_with_planned_time_only(self, mock_coordinator):
        """Test native_value returns planned departure time when actual not available."""
        departure_planned = datetime(2023, 12, 25, 14, 25)

        trip = MockTrip(
            departure_time_planned=departure_planned,
            departure_time_actual=None,
        )

        mock_coordinator.data = {
            "routes": {"test_route": {"route": {}, "next_trip": trip}}
        }
        route = {CONF_NAME: "Test Route"}
        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route)

        assert sensor.native_value == "14:25"

    def test_native_value_no_times(self, mock_coordinator):
        """Test native_value when trip has no departure times."""
        trip = MockTrip(
            departure_time_planned=None,
            departure_time_actual=None,
        )

        mock_coordinator.data = {
            "routes": {"test_route": {"route": {}, "next_trip": trip}}
        }
        route = {CONF_NAME: "Test Route"}
        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route)

        assert sensor.native_value is None

    def test_extra_state_attributes_no_coordinator_data(self, mock_coordinator):
        """Test extra_state_attributes when coordinator has no data."""
        mock_coordinator.data = None
        route = {CONF_NAME: "Test Route"}
        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route)

        assert sensor.extra_state_attributes is None

    def test_extra_state_attributes_no_routes(self, mock_coordinator):
        """Test extra_state_attributes when coordinator data has no routes."""
        mock_coordinator.data = {"other_data": "value"}
        route = {CONF_NAME: "Test Route"}
        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route)

        assert sensor.extra_state_attributes is None

    def test_extra_state_attributes_no_route_data(self, mock_coordinator):
        """Test extra_state_attributes when specific route has no data."""
        mock_coordinator.data = {"routes": {"other_route": {}}}
        route = {CONF_NAME: "Test Route"}
        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route)

        assert sensor.extra_state_attributes is None

    def test_extra_state_attributes_no_next_trip(self, mock_coordinator):
        """Test extra_state_attributes when route has no next trip."""
        mock_coordinator.data = {
            "routes": {"test_route": {"route": {}, "next_trip": None}}
        }
        route = {CONF_NAME: "Test Route"}
        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route)

        assert sensor.extra_state_attributes is None

    def test_extra_state_attributes_full_trip(self, mock_coordinator):
        """Test extra_state_attributes with complete trip information."""
        departure_actual = datetime(2023, 12, 25, 14, 30)
        departure_planned = datetime(2023, 12, 25, 14, 25)

        trip = MockTrip(
            going=True,
            departure_time_actual=departure_actual,
            departure_time_planned=departure_planned,
            departure_platform_planned="3a",
            departure_platform_actual="3b",
            status="ON_TIME",
        )

        route_info = {CONF_NAME: "Test Route", "from": "RTD", "to": "ASD"}

        mock_coordinator.data = {
            "routes": {
                "test_route": {
                    "route": route_info,
                    "next_trip": trip,
                    "trips": [trip],
                }
            }
        }

        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route_info)
        attributes = sensor.extra_state_attributes

        assert attributes is not None
        assert attributes["going"] is True
        assert attributes["departure_time_planned"] == departure_planned
        assert attributes["departure_time_actual"] == departure_actual
        assert attributes["departure_delay"] is True
        assert attributes["departure_delay_minutes"] == 5
        assert attributes["departure_platform_planned"] == "3a"
        assert attributes["departure_platform_actual"] == "3b"
        assert attributes["route"] == route_info

        # Check trips information
        assert "trips" in attributes
        assert len(attributes["trips"]) == 1
        trip_info = attributes["trips"][0]
        assert trip_info["departure_time_planned"] == departure_planned
        assert trip_info["departure_time_actual"] == departure_actual
        assert trip_info["departure_platform_planned"] == "3a"
        assert trip_info["departure_platform_actual"] == "3b"
        assert trip_info["status"] == "ON_TIME"

    def test_extra_state_attributes_no_delay(self, mock_coordinator):
        """Test extra_state_attributes when departure times are the same (no delay)."""
        departure_time = datetime(2023, 12, 25, 14, 30)

        trip = MockTrip(
            departure_time_actual=departure_time,
            departure_time_planned=departure_time,
        )

        route_info = {CONF_NAME: "Test Route"}

        mock_coordinator.data = {
            "routes": {
                "test_route": {
                    "route": route_info,
                    "next_trip": trip,
                }
            }
        }

        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route_info)
        attributes = sensor.extra_state_attributes

        assert attributes is not None
        assert attributes["departure_delay"] is False
        assert attributes["departure_delay_minutes"] == 0

    def test_extra_state_attributes_early_departure(self, mock_coordinator):
        """Test extra_state_attributes when train departs early."""
        departure_actual = datetime(2023, 12, 25, 14, 20)
        departure_planned = datetime(2023, 12, 25, 14, 25)

        trip = MockTrip(
            departure_time_actual=departure_actual,
            departure_time_planned=departure_planned,
        )

        route_info = {CONF_NAME: "Test Route"}

        mock_coordinator.data = {
            "routes": {
                "test_route": {
                    "route": route_info,
                    "next_trip": trip,
                }
            }
        }

        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route_info)
        attributes = sensor.extra_state_attributes

        assert attributes is not None
        assert attributes["departure_delay"] is False
        assert attributes["departure_delay_minutes"] == -5

    def test_extra_state_attributes_missing_times(self, mock_coordinator):
        """Test extra_state_attributes when some time information is missing."""
        trip = MockTrip(
            departure_time_planned=datetime(2023, 12, 25, 14, 25),
            departure_time_actual=None,
        )

        route_info = {CONF_NAME: "Test Route"}

        mock_coordinator.data = {
            "routes": {
                "test_route": {
                    "route": route_info,
                    "next_trip": trip,
                }
            }
        }

        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route_info)
        attributes = sensor.extra_state_attributes

        assert attributes is not None
        assert attributes["departure_delay"] is False
        assert "departure_delay_minutes" not in attributes

    def test_extra_state_attributes_multiple_trips(self, mock_coordinator):
        """Test extra_state_attributes with multiple trips (should limit to 5)."""
        base_time = datetime(2023, 12, 25, 14, 0)
        trips = [
            MockTrip(
                departure_time_planned=base_time + timedelta(minutes=i * 30),
                status=f"TRIP_{i}",
            )
            for i in range(10)  # Create 10 trips
        ]

        route_info = {CONF_NAME: "Test Route"}

        mock_coordinator.data = {
            "routes": {
                "test_route": {
                    "route": route_info,
                    "next_trip": trips[0],
                    "trips": trips,
                }
            }
        }

        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route_info)
        attributes = sensor.extra_state_attributes

        # Should only include first 5 trips
        assert attributes is not None
        assert "trips" in attributes
        assert len(attributes["trips"]) == 5

        # Verify they are the first 5 trips
        for i in range(5):
            assert attributes["trips"][i]["status"] == f"TRIP_{i}"

    def test_extra_state_attributes_partial_trip_info(self, mock_coordinator):
        """Test extra_state_attributes with trip missing some attributes."""

        # Create a trip with only some attributes
        class PartialTrip:
            def __init__(self) -> None:
                self.going = False
                # Deliberately don't set departure_time_* attributes

        trip = PartialTrip()

        route_info = {CONF_NAME: "Test Route"}

        mock_coordinator.data = {
            "routes": {
                "test_route": {
                    "route": route_info,
                    "next_trip": trip,
                    "trips": [trip],
                }
            }
        }

        sensor = NSCoordinatorSensor(mock_coordinator, "test_route", route_info)
        attributes = sensor.extra_state_attributes

        # Should handle missing attributes gracefully
        assert attributes is not None
        if attributes is not None:
            assert attributes["going"] is False
            assert attributes["departure_delay"] is False
            assert attributes["route"] == route_info

            # trips should handle missing attributes with None values
            assert "trips" in attributes
            trip_info = attributes["trips"][0]
            assert trip_info["departure_time_planned"] is None
            assert trip_info["status"] is None


async def test_async_setup_platform_legacy_warning(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that legacy platform setup logs a warning."""
    async_add_entities = Mock()

    await async_setup_platform(hass, {}, async_add_entities, None)

    # Should not add any entities
    async_add_entities.assert_not_called()

    # Should log a deprecation warning
    assert (
        "Platform-based configuration for Nederlandse Spoorwegen is no longer supported"
        in caplog.text
    )
    assert (
        "Please remove the 'nederlandse_spoorwegen' platform from your sensor configuration"
        in caplog.text
    )
    assert "automatically migrated to config entries" in caplog.text
