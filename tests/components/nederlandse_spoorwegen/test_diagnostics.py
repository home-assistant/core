"""Test Nederlandse Spoorwegen diagnostics."""

from unittest.mock import MagicMock

from homeassistant.components.nederlandse_spoorwegen import DOMAIN, NSRuntimeData
from homeassistant.components.nederlandse_spoorwegen.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant


async def test_config_entry_diagnostics(hass: HomeAssistant) -> None:
    """Test config entry diagnostics."""
    # Create mock coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.last_exception = None
    mock_coordinator.data = {
        "routes": {
            "Test Route_AMS_UTR": {
                "route": {
                    "name": "Test Route",
                    "from": "AMS",
                    "to": "UTR",
                    "via": None,
                },
                "first_trip": {
                    "departure_time_planned": "2024-01-01T10:00:00",
                    "departure_platform_planned": "5",
                    "arrival_time_planned": "2024-01-01T11:00:00",
                    "status": "ON_TIME",
                    "nr_transfers": 0,
                },
                "next_trip": {
                    "departure_time_planned": "2024-01-01T10:30:00",
                },
            }
        },
        "stations": [
            type("Station", (), {"code": "AMS", "name": "Amsterdam Centraal"})(),
            type("Station", (), {"code": "UTR", "name": "Utrecht Centraal"})(),
        ],
        "last_updated": "2024-01-01T09:00:00",
    }

    # Create mock config entry
    mock_config_entry = MagicMock()
    mock_config_entry.data = {CONF_API_KEY: "test_api_key"}
    mock_config_entry.entry_id = "test_entry_id"
    mock_config_entry.title = "Test NS Integration"
    mock_config_entry.domain = DOMAIN
    mock_config_entry.as_dict.return_value = {
        "entry_id": "test_entry_id",
        "data": {CONF_API_KEY: "test_api_key"},
        "title": "Test NS Integration",
        "domain": DOMAIN,
    }

    # Create mock subentry
    mock_subentry = MagicMock()
    mock_subentry.data = {
        "name": "Test Route",
        "from": "AMS",
        "to": "UTR",
        "via": None,
    }
    mock_subentry.as_dict.return_value = {
        "entry_id": "subentry_id",
        "data": mock_subentry.data,
    }

    mock_config_entry.subentries = {"subentry_id": mock_subentry}

    # Create runtime data
    runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=[
            type("Station", (), {"code": "AMS", "name": "Amsterdam Centraal"})(),
            type("Station", (), {"code": "UTR", "name": "Utrecht Centraal"})(),
        ],
        stations_updated="2024-01-01T08:00:00",
    )
    mock_config_entry.runtime_data = runtime_data

    # Get diagnostics
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Verify structure
    assert "entry" in diagnostics
    assert "coordinator_data" in diagnostics
    assert "coordinator_status" in diagnostics
    assert "runtime_data" in diagnostics
    assert "subentries" in diagnostics
    assert "integration_health" in diagnostics

    # Verify sensitive data is redacted
    assert "test_api_key" not in str(diagnostics["entry"])

    # Verify coordinator data structure
    coordinator_data = diagnostics["coordinator_data"]
    assert "routes" in coordinator_data
    assert "stations" in coordinator_data
    assert len(coordinator_data["routes"]) == 1

    # Verify route data is properly sanitized
    route_data = coordinator_data["routes"]["route_1"]
    assert "route" in route_data
    assert route_data["route"]["name"] == "redacted"
    assert route_data["route"]["from"] == "AMS"  # Station codes are public data
    assert route_data["route"]["to"] == "UTR"  # Station codes are public data
    assert route_data["has_first_trip"] is True
    assert route_data["has_next_trip"] is True

    # Verify trip structure information
    assert "first_trip_structure" in route_data
    trip_structure = route_data["first_trip_structure"]
    assert trip_structure["has_departure_time"] is True
    assert trip_structure["has_platform_info"] is True
    assert trip_structure["has_status"] is True

    # Verify subentry information
    assert len(diagnostics["subentries"]) == 1
    subentry_data = diagnostics["subentries"]["subentry_1"]
    assert "subentry_info" in subentry_data
    assert "route_config" in subentry_data
    assert subentry_data["route_config"]["name"] == "redacted"

    # Verify integration health
    health = diagnostics["integration_health"]
    assert health["coordinator_available"] is True
    assert health["coordinator_has_data"] is True
    assert health["routes_configured"] == 1
    assert health["api_connection_status"] == "healthy"


async def test_config_entry_diagnostics_no_data(hass: HomeAssistant) -> None:
    """Test config entry diagnostics when coordinator has no data."""
    # Create mock coordinator without data
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = False
    mock_coordinator.data = None

    # Create mock config entry
    mock_config_entry = MagicMock()
    mock_config_entry.data = {CONF_API_KEY: "test_api_key"}
    mock_config_entry.as_dict.return_value = {
        "entry_id": "test_entry_id",
        "data": {CONF_API_KEY: "test_api_key"},
    }
    mock_config_entry.subentries = {}

    # Create runtime data
    runtime_data = NSRuntimeData(coordinator=mock_coordinator)
    mock_config_entry.runtime_data = runtime_data

    # Get diagnostics
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Verify coordinator data is None
    assert diagnostics["coordinator_data"] is None
    assert diagnostics["integration_health"]["coordinator_has_data"] is False
    assert diagnostics["integration_health"]["api_connection_status"] == "issues"


async def test_device_diagnostics(hass: HomeAssistant) -> None:
    """Test device diagnostics."""
    # Create mock coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
        "routes": {
            "Test Route_AMS_UTR": {
                "route": {"name": "Test Route", "from": "AMS", "to": "UTR"},
                "first_trip": {
                    "departure_time_planned": "2024-01-01T10:00:00",
                    "departure_platform_planned": "5",
                    "status": "ON_TIME",
                },
            }
        }
    }

    # Create mock config entry
    mock_config_entry = MagicMock()
    mock_config_entry.data = {CONF_API_KEY: "test_api_key"}
    mock_config_entry.entry_id = "test_entry_id"
    mock_config_entry.domain = DOMAIN

    # Create mock subentry
    mock_subentry = MagicMock()
    mock_subentry.data = {
        "name": "Test Route",
        "from": "AMS",
        "to": "UTR",
    }
    mock_subentry.subentry_id = "subentry_id"

    mock_config_entry.subentries = {"subentry_id": mock_subentry}

    # Create runtime data
    runtime_data = NSRuntimeData(coordinator=mock_coordinator)
    mock_config_entry.runtime_data = runtime_data

    # Create mock device
    mock_device = MagicMock()
    mock_device.name = "Test Route"
    mock_device.manufacturer = "Nederlandse Spoorwegen"
    mock_device.model = "NS Route"
    mock_device.sw_version = "1.0"
    mock_device.identifiers = {(DOMAIN, "subentry_id")}

    # Get device diagnostics
    diagnostics = await async_get_device_diagnostics(
        hass, mock_config_entry, mock_device
    )

    # Verify structure
    assert "device_info" in diagnostics
    assert "route_config" in diagnostics
    assert "route_data_status" in diagnostics

    # Verify device info
    device_info = diagnostics["device_info"]
    assert device_info["name"] == "Test Route"
    assert device_info["manufacturer"] == "Nederlandse Spoorwegen"

    # Verify route config is redacted
    route_config = diagnostics["route_config"]
    assert route_config["name"] == "redacted"
    assert route_config["from"] == "AMS"  # Station codes are public data
    assert route_config["to"] == "UTR"  # Station codes are public data

    # Verify route data status
    route_data_status = diagnostics["route_data_status"]
    assert route_data_status["has_data"] is True
    assert "data_structure" in route_data_status
    assert route_data_status["data_structure"]["has_first_trip"] is True

    # Verify trip structure
    assert "first_trip_structure" in route_data_status
    trip_structure = route_data_status["first_trip_structure"]
    assert "timing_data" in trip_structure
    assert "platform_data" in trip_structure


async def test_device_diagnostics_no_matching_subentry(hass: HomeAssistant) -> None:
    """Test device diagnostics when no matching subentry is found."""
    # Create mock coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"routes": {}}

    # Create mock config entry
    mock_config_entry = MagicMock()
    mock_config_entry.data = {CONF_API_KEY: "test_api_key"}
    mock_config_entry.entry_id = "test_entry_id"
    mock_config_entry.domain = DOMAIN
    mock_config_entry.subentries = {}

    # Create runtime data
    runtime_data = NSRuntimeData(coordinator=mock_coordinator)
    mock_config_entry.runtime_data = runtime_data

    # Create mock device with non-matching identifiers
    mock_device = MagicMock()
    mock_device.name = "Unknown Route"
    mock_device.manufacturer = "Nederlandse Spoorwegen"
    mock_device.model = "NS Route"
    mock_device.sw_version = "1.0"
    mock_device.identifiers = {(DOMAIN, "unknown_id")}

    # Get device diagnostics
    diagnostics = await async_get_device_diagnostics(
        hass, mock_config_entry, mock_device
    )

    # Verify structure
    assert "device_info" in diagnostics
    assert "route_config" in diagnostics
    assert "route_data_status" in diagnostics

    # Verify route config is empty
    assert diagnostics["route_config"] == {}
    assert diagnostics["route_data_status"]["has_data"] is False


async def test_diagnostics_with_no_trip_data(hass: HomeAssistant) -> None:
    """Test diagnostics when route has no trip data."""
    # Create mock coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.last_exception = None
    mock_coordinator.data = {
        "routes": {
            "Test Route_AMS_UTR": {
                "route": {"name": "Test Route", "from": "AMS", "to": "UTR"},
                # No trip data
            }
        },
        "stations": [],
    }

    # Create mock config entry
    mock_config_entry = MagicMock()
    mock_config_entry.data = {CONF_API_KEY: "test_api_key"}
    mock_config_entry.as_dict.return_value = {
        "entry_id": "test_entry_id",
        "data": {CONF_API_KEY: "test_api_key"},
    }
    mock_config_entry.subentries = {}

    # Create runtime data
    runtime_data = NSRuntimeData(coordinator=mock_coordinator)
    mock_config_entry.runtime_data = runtime_data

    # Get diagnostics
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Verify route data structure
    coordinator_data = diagnostics["coordinator_data"]
    route_data = coordinator_data["routes"]["route_1"]
    assert route_data["has_first_trip"] is False
    assert route_data["has_next_trip"] is False
    assert "first_trip_structure" not in route_data
