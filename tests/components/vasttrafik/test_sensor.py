"""Test the Västtrafik sensor platform."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest

import vasttrafik

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.vasttrafik.const import DOMAIN
from homeassistant.const import (
    CONF_DELAY,
    CONF_NAME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import now

from tests.common import MockConfigEntry


# Test data fixtures based on Västtrafik API v4 schema
@pytest.fixture
def mock_departure_board_data():
    """Mock departure board API response following v4 schema."""
    return [
        {
            "detailsReference": "ref_123",
            "serviceJourney": {
                "gid": "9015014500100001",
                "origin": "Centralstationen",
                "direction": "Angered",
                "line": {
                    "gid": "9011014500100000",
                    "name": "Spårvagn 1",
                    "shortName": "1",
                    "designation": "1",
                    "backgroundColor": "#007AC7",
                    "foregroundColor": "#FFFFFF",
                    "borderColor": "#007AC7",
                    "transportMode": "tram",
                    "isWheelchairAccessible": True,
                },
            },
            "stopPoint": {
                "gid": "9022014001960001",
                "name": "Centralstationen",
                "platform": "A",
            },
            "plannedTime": (now() + timedelta(minutes=5)).isoformat(),
            "estimatedTime": (now() + timedelta(minutes=6)).isoformat(),
            "estimatedOtherwisePlannedTime": (now() + timedelta(minutes=6)).isoformat(),
            "isCancelled": False,
            "isPartCancelled": False,
        },
        {
            "detailsReference": "ref_124", 
            "serviceJourney": {
                "gid": "9015014500200001",
                "origin": "Centralstationen", 
                "direction": "Frölunda",
                "line": {
                    "gid": "9011014500200000",
                    "name": "Spårvagn 2",
                    "shortName": "2",
                    "designation": "2", 
                    "backgroundColor": "#00AA4F",
                    "foregroundColor": "#FFFFFF",
                    "borderColor": "#00AA4F",
                    "transportMode": "tram",
                    "isWheelchairAccessible": False,
                },
            },
            "stopPoint": {
                "gid": "9022014001960002",
                "name": "Centralstationen",
                "platform": "B",
            },
            "plannedTime": (now() + timedelta(minutes=8)).isoformat(),
            "estimatedTime": None,
            "estimatedOtherwisePlannedTime": (now() + timedelta(minutes=8)).isoformat(),
            "isCancelled": False,
            "isPartCancelled": False,
        },
        {
            "detailsReference": "ref_125",
            "serviceJourney": {
                "gid": "9015014500100002", 
                "origin": "Centralstationen",
                "direction": "Angered",
                "line": {
                    "gid": "9011014500100000",
                    "name": "Spårvagn 1", 
                    "shortName": "1",
                    "designation": "1",
                    "backgroundColor": "#007AC7",
                    "foregroundColor": "#FFFFFF", 
                    "borderColor": "#007AC7",
                    "transportMode": "tram",
                    "isWheelchairAccessible": True,
                },
            },
            "stopPoint": {
                "gid": "9022014001960001",
                "name": "Centralstationen", 
                "platform": "A",
            },
            "plannedTime": (now() + timedelta(minutes=15)).isoformat(),
            "estimatedTime": None,
            "estimatedOtherwisePlannedTime": (now() + timedelta(minutes=15)).isoformat(),
            "isCancelled": False,
            "isPartCancelled": False,
        },
    ]


@pytest.fixture
def mock_location_data():
    """Mock location search API response."""
    return [{"gid": "9021014001960000", "name": "Centralstationen"}]


@pytest.fixture
def mock_vasttrafik_planner(mock_departure_board_data, mock_location_data):
    """Mock Västtrafik JournyPlanner."""
    planner = MagicMock(spec=vasttrafik.JournyPlanner)
    planner.location_name.return_value = mock_location_data
    planner.departureboard.return_value = mock_departure_board_data
    return planner


@pytest.fixture
def main_config_entry():
    """Main integration config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Västtrafik",
        data={"key": "test-key", "secret": "test-secret", "is_departure_board": False},
        unique_id="vasttrafik_main",
    )


@pytest.fixture  
def departure_board_config_entry():
    """Departure board config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Departure: Centralstationen",
        data={
            "from": "Centralstationen",
            "name": "Central Departures", 
            "heading": "",
            "lines": ["1", "2"],
            "tracks": ["A"],
            "delay": 5,
            "is_departure_board": True,
        },
        unique_id="vasttrafik_departure_centralstationen",
    )


@pytest.fixture
async def setup_main_integration(
    hass: HomeAssistant, main_config_entry, mock_vasttrafik_planner
):
    """Set up the main integration."""
    main_config_entry.add_to_hass(hass)
    
    with patch(
        "homeassistant.components.vasttrafik.vasttrafik.JournyPlanner"
    ) as mock_planner_class:
        mock_planner_class.return_value = mock_vasttrafik_planner
        await hass.config_entries.async_setup(main_config_entry.entry_id)
        await hass.async_block_till_done()
    
    return main_config_entry


@pytest.fixture
async def setup_departure_board_integration(
    hass: HomeAssistant, setup_main_integration, departure_board_config_entry
):
    """Set up departure board integration."""
    departure_board_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(departure_board_config_entry.entry_id)
    await hass.async_block_till_done()
    return departure_board_config_entry


class TestVasttrafikStatusSensor:
    """Test the Västtrafik status sensor."""

    async def test_status_sensor_setup(
        self, hass: HomeAssistant, setup_main_integration, entity_registry: er.EntityRegistry
    ):
        """Test that status sensor is created properly."""
        state = hass.states.get("sensor.vasttrafik_api_status")
        assert state is not None
        assert state.name == "Västtrafik API Status"

        # Check entity registry
        entity = entity_registry.async_get("sensor.vasttrafik_api_status")
        assert entity is not None
        assert entity.unique_id == f"{setup_main_integration.entry_id}_status"

    async def test_status_sensor_connected_state(
        self, hass: HomeAssistant, setup_main_integration, mock_vasttrafik_planner
    ):
        """Test status sensor shows connected state."""
        state = hass.states.get("sensor.vasttrafik_api_status")
        assert state.state == "Connected"
        assert state.attributes.get("attribution") == "Data provided by Västtrafik"
        assert state.attributes.get("icon") == "mdi:train"

    async def test_status_sensor_connection_error(
        self, hass: HomeAssistant, main_config_entry
    ):
        """Test status sensor handles connection errors."""
        # Set up mock planner with error  
        error_planner = MagicMock(spec=vasttrafik.JournyPlanner)
        error_planner.location_name.side_effect = vasttrafik.Error("API Error")
        
        main_config_entry.add_to_hass(hass)
        
        with patch(
            "homeassistant.components.vasttrafik.vasttrafik.JournyPlanner"
        ) as mock_planner_class:
            mock_planner_class.return_value = error_planner
            await hass.config_entries.async_setup(main_config_entry.entry_id)
            await hass.async_block_till_done()
        
        state = hass.states.get("sensor.vasttrafik_api_status")
        assert state.state == "Disconnected"

    async def test_status_sensor_unexpected_error(
        self, hass: HomeAssistant, main_config_entry
    ):
        """Test status sensor handles unexpected errors."""
        # Set up mock planner with unexpected error
        error_planner = MagicMock(spec=vasttrafik.JournyPlanner)
        error_planner.location_name.side_effect = Exception("Unexpected error")
        
        main_config_entry.add_to_hass(hass)
        
        with patch(
            "homeassistant.components.vasttrafik.vasttrafik.JournyPlanner"
        ) as mock_planner_class:
            mock_planner_class.return_value = error_planner
            await hass.config_entries.async_setup(main_config_entry.entry_id)
            await hass.async_block_till_done()
        
        state = hass.states.get("sensor.vasttrafik_api_status")
        assert state.state == "Error"

    async def test_status_sensor_device_info(
        self, hass: HomeAssistant, setup_main_integration, device_registry: dr.DeviceRegistry
    ):
        """Test status sensor device info."""
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, setup_main_integration.entry_id)}
        )
        assert device is not None
        assert device.name == "Västtrafik API"
        assert device.manufacturer == "Västtrafik"
        assert device.model == "Public Transport API"
        assert device.entry_type == "service"


class TestVasttrafikDepartureSensor:
    """Test the Västtrafik departure sensor."""

    async def test_departure_sensor_setup(
        self,
        hass: HomeAssistant,
        setup_departure_board_integration,
        entity_registry: er.EntityRegistry,
    ):
        """Test that departure sensor is created properly."""
        state = hass.states.get("sensor.centralstationen_departure_board_central_departures")
        assert state is not None
        assert state.name == "Centralstationen Departure Board Central Departures"

        # Check entity registry
        entity = entity_registry.async_get("sensor.centralstationen_departure_board_central_departures")
        assert entity is not None

    async def test_departure_sensor_state_and_attributes(
        self,
        hass: HomeAssistant,
        setup_departure_board_integration,
        mock_vasttrafik_planner,
    ):
        """Test departure sensor state and attributes."""
        state = hass.states.get("sensor.centralstationen_departure_board_central_departures")
        
        # Should show the next departure time (first valid departure after filtering) 
        # Based on our mock data: first departure is line 1 at +6 minutes (estimated time)
        expected_time = (now() + timedelta(minutes=6)).strftime("%H:%M")
        assert state.state == expected_time
        
        # Check attributes
        attributes = state.attributes
        assert attributes.get("station") == "Centralstationen"
        assert attributes.get("destination") == "Any direction"
        assert attributes.get("line_filter") == ["1", "2"]
        assert attributes.get("track_filter") == ["A"]
        assert attributes.get("delay_minutes") == 5
        
        # Check departures list (should be filtered by lines and tracks)
        departures = attributes.get("departures", [])
        assert len(departures) >= 1
        
        # First departure should match line 1, track A (from our mock data)
        first_departure = departures[0]
        assert first_departure["line"] == "1"
        assert first_departure["track"] == "A"
        assert first_departure["direction"] == "Angered"
        assert first_departure["accessibility"] == "wheelChair"
        assert first_departure["line_color"] == "#007AC7"
        assert first_departure["line_text_color"] == "#FFFFFF"

    async def test_departure_sensor_no_departures(
        self, hass: HomeAssistant
    ):
        """Test departure sensor when no departures are available."""
        # Set up with empty departure board
        empty_planner = MagicMock(spec=vasttrafik.JournyPlanner) 
        empty_planner.location_name.return_value = [{"gid": "9021014001960000", "name": "Centralstationen"}]
        empty_planner.departureboard.return_value = []
        
        # Create fresh config entries for this test
        main_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Västtrafik",
            data={"key": "test-key", "secret": "test-secret", "is_departure_board": False},
            unique_id="vasttrafik_main_empty",
        )
        departure_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Departure: Centralstationen",
            data={
                "from": "Centralstationen",
                "name": "Central Departures", 
                "heading": "",
                "lines": ["1", "2"],
                "tracks": ["A"],
                "delay": 5,
                "is_departure_board": True,
            },
            unique_id="vasttrafik_departure_centralstationen_empty",
        )
        
        main_entry.add_to_hass(hass)
        
        with patch(
            "homeassistant.components.vasttrafik.vasttrafik.JournyPlanner"
        ) as mock_planner_class:
            mock_planner_class.return_value = empty_planner
            await hass.config_entries.async_setup(main_entry.entry_id)
            await hass.async_block_till_done()
            
            # Now add departure entry after main is loaded
            departure_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(departure_entry.entry_id)
            await hass.async_block_till_done()
        
        state = hass.states.get("sensor.centralstationen_departure_board_central_departures")
        # The sensor state should be "unknown" on first setup before any update
        assert state.state == "unknown"
        # No departures attribute should be set yet 
        assert state.attributes.get("departures") is None

    async def test_departure_sensor_api_error(
        self, hass: HomeAssistant
    ):
        """Test departure sensor handles API errors."""
        # Set up with API error
        error_planner = MagicMock(spec=vasttrafik.JournyPlanner)
        error_planner.location_name.return_value = [{"gid": "9021014001960000", "name": "Centralstationen"}]
        error_planner.departureboard.side_effect = vasttrafik.Error("API Error")
        
        # Create fresh config entries for this test
        main_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Västtrafik",
            data={"key": "test-key", "secret": "test-secret", "is_departure_board": False},
            unique_id="vasttrafik_main_error",
        )
        departure_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Departure: Centralstationen",
            data={
                "from": "Centralstationen",
                "name": "Central Departures", 
                "heading": "",
                "lines": ["1", "2"],
                "tracks": ["A"],
                "delay": 5,
                "is_departure_board": True,
            },
            unique_id="vasttrafik_departure_centralstationen_error",
        )
        
        main_entry.add_to_hass(hass)
        
        with patch(
            "homeassistant.components.vasttrafik.vasttrafik.JournyPlanner"
        ) as mock_planner_class:
            mock_planner_class.return_value = error_planner
            await hass.config_entries.async_setup(main_entry.entry_id)
            await hass.async_block_till_done()
            
            # Now add departure entry after main is loaded
            departure_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(departure_entry.entry_id)
            await hass.async_block_till_done()
        
        state = hass.states.get("sensor.centralstationen_departure_board_central_departures")
        # The sensor state should be "unknown" on first setup before any update
        assert state.state == "unknown"
        # No departures attribute should be set yet
        assert state.attributes.get("departures") is None