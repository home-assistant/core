"""Test diagnostics for Autoskope integration."""

from unittest.mock import MagicMock

from homeassistant.components.autoskope.const import DOMAIN
from homeassistant.components.autoskope.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_diagnostics(hass: HomeAssistant) -> None:
    """Test diagnostics data."""
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id="test_entry", title="Autoskope Test"
    )
    entry.add_to_hass(hass)

    # Mock vehicle position with all attributes
    mock_position = MagicMock(
        latitude=12.34,
        longitude=56.78,
        speed=50.0,
        timestamp="2024-01-01T12:00:00Z",
        park_mode=False,
    )

    # Mock vehicle with all attributes
    mock_vehicle = MagicMock()
    mock_vehicle.id = "vehicle_123"
    mock_vehicle.name = "Test Vehicle"
    mock_vehicle.position = mock_position
    mock_vehicle.battery_voltage = 4.1
    mock_vehicle.external_voltage = 12.5

    # Mock coordinator with data and status
    coordinator = MagicMock()
    coordinator.data = {"vehicle_123": mock_vehicle}
    coordinator.last_update_success = True

    # Set up hass.data correctly with the "coordinator" key
    hass.data[DOMAIN] = {entry.entry_id: {"coordinator": coordinator}}

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # Update assertion to include all expected fields
    assert diagnostics == {
        "entry": {
            "entry_id": "test_entry",
            "title": "Autoskope Test",
        },
        "vehicles": [
            {
                "id": "vehicle_123",
                "name": "Test Vehicle",
                "latitude": 12.34,
                "longitude": 56.78,
                "speed": 50.0,
                "timestamp": "2024-01-01T12:00:00Z",
                "park_mode": False,
                "battery_voltage": 4.1,
                "external_voltage": 12.5,
            }
        ],
        "coordinator_status": {
            "last_update_success": True,
        },
    }


async def test_diagnostics_no_position(hass: HomeAssistant) -> None:
    """Test diagnostics data when vehicle position is None."""
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id="test_entry", title="Autoskope Test"
    )
    entry.add_to_hass(hass)

    # Mock vehicle with position set to None
    mock_vehicle = MagicMock()
    mock_vehicle.id = "vehicle_456"
    mock_vehicle.name = "No Position Vehicle"
    mock_vehicle.position = None
    mock_vehicle.battery_voltage = 3.9
    mock_vehicle.external_voltage = 12.1

    # Mock coordinator
    coordinator = MagicMock()
    coordinator.data = {"vehicle_456": mock_vehicle}
    coordinator.last_update_success = False

    # Set up hass.data
    hass.data[DOMAIN] = {entry.entry_id: {"coordinator": coordinator}}

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # Assert position-related fields are None
    assert diagnostics == {
        "entry": {
            "entry_id": "test_entry",
            "title": "Autoskope Test",
        },
        "vehicles": [
            {
                "id": "vehicle_456",
                "name": "No Position Vehicle",
                "latitude": None,
                "longitude": None,
                "speed": None,
                "timestamp": None,
                "park_mode": None,
                "battery_voltage": 3.9,
                "external_voltage": 12.1,
            }
        ],
        "coordinator_status": {
            "last_update_success": False,
        },
    }


async def test_diagnostics_no_coordinator_data(hass: HomeAssistant) -> None:
    """Test diagnostics data when coordinator data is None."""
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id="test_entry", title="Autoskope Test"
    )
    entry.add_to_hass(hass)

    # Mock coordinator with data set to None
    coordinator = MagicMock()
    coordinator.data = None
    coordinator.last_update_success = False

    # Set up hass.data
    hass.data[DOMAIN] = {entry.entry_id: {"coordinator": coordinator}}

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # Assert vehicles list is empty
    assert diagnostics == {
        "entry": {
            "entry_id": "test_entry",
            "title": "Autoskope Test",
        },
        "vehicles": [],
        "coordinator_status": {
            "last_update_success": False,
        },
    }
