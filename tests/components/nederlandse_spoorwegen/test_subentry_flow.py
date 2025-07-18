"""Test subentry flow for Nederlandse Spoorwegen integration."""

from unittest.mock import MagicMock

from homeassistant.components.nederlandse_spoorwegen import NSRuntimeData, config_flow
from homeassistant.config_entries import ConfigSubentryFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

API_KEY = "abc1234567"


async def test_subentry_flow_handler_exists() -> None:
    """Test that RouteSubentryFlowHandler is properly implemented."""
    assert hasattr(config_flow, "RouteSubentryFlowHandler")
    assert issubclass(config_flow.RouteSubentryFlowHandler, ConfigSubentryFlow)


async def test_config_flow_supports_subentries() -> None:
    """Test that the config flow supports route subentries."""
    # Create a mock config entry
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    flow_handler = config_flow.NSConfigFlow()

    supported_types = flow_handler.async_get_supported_subentry_types(mock_config_entry)

    assert "route" in supported_types
    assert supported_types["route"] == config_flow.RouteSubentryFlowHandler


async def test_subentry_flow_handler_initialization(hass: HomeAssistant) -> None:
    """Test that the subentry flow handler can be initialized properly."""
    # Create a mock config entry
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")

    # Test that it has the required methods
    assert hasattr(handler, "async_step_user")
    assert hasattr(handler, "async_step_reconfigure")
    assert hasattr(handler, "_async_step_route_form")
    assert hasattr(handler, "_ensure_stations_available")
    assert hasattr(handler, "_get_station_options")


async def test_subentry_flow_handler_form_creation(hass: HomeAssistant) -> None:
    """Test that the subentry flow handler can create forms properly."""
    # Create a mock config entry with stations data
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Mock runtime data with stations
    mock_coordinator = MagicMock()
    mock_runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=[
            {"code": "AMS", "name": "Amsterdam Centraal"},
            {"code": "UTR", "name": "Utrecht Centraal"},
        ],
        stations_updated="2024-01-01T00:00:00Z",
    )

    # Set runtime_data directly on the mock config entry
    mock_config_entry.runtime_data = mock_runtime_data

    # Add to hass data
    hass.data.setdefault("nederlandse_spoorwegen", {})[mock_config_entry.entry_id] = (
        mock_runtime_data
    )

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")

    # Mock the _get_entry method to return our mock config entry
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Test the form creation
    result = await handler.async_step_user()

    assert result.get("type") == "form"
    assert result.get("step_id") == "user"
    assert "data_schema" in result


async def test_subentry_flow_add_route_success(hass: HomeAssistant) -> None:
    """Test successfully adding a route through subentry flow."""
    # Create a mock config entry with stations data
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Mock runtime data with stations
    mock_coordinator = MagicMock()
    mock_runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=[
            {"code": "AMS", "name": "Amsterdam Centraal"},
            {"code": "UTR", "name": "Utrecht Centraal"},
            {"code": "GVC", "name": "Den Haag Centraal"},
        ],
        stations_updated="2024-01-01T00:00:00Z",
    )

    # Set runtime_data directly on the mock config entry
    mock_config_entry.runtime_data = mock_runtime_data

    # Add to hass data
    hass.data.setdefault("nederlandse_spoorwegen", {})[mock_config_entry.entry_id] = (
        mock_runtime_data
    )

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")
    handler.context = {"source": "user"}  # Required for async_create_entry

    # Mock the _get_entry method to return our mock config entry
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Test successful route creation
    result = await handler.async_step_user(
        user_input={
            "name": "Test Route",
            "from": "AMS",
            "to": "UTR",
            "via": "",
            "time": "",
        }
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Test Route"
    assert result.get("data") == {
        "name": "Test Route",
        "from": "AMS",
        "to": "UTR",
    }


async def test_subentry_flow_add_route_with_via_and_time(hass: HomeAssistant) -> None:
    """Test adding a route with via station and time through subentry flow."""
    # Create a mock config entry with stations data
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Mock runtime data with stations
    mock_coordinator = MagicMock()
    mock_runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=[
            {"code": "AMS", "name": "Amsterdam Centraal"},
            {"code": "UTR", "name": "Utrecht Centraal"},
            {"code": "GVC", "name": "Den Haag Centraal"},
        ],
        stations_updated="2024-01-01T00:00:00Z",
    )

    # Set runtime_data directly on the mock config entry
    mock_config_entry.runtime_data = mock_runtime_data

    # Add to hass data
    hass.data.setdefault("nederlandse_spoorwegen", {})[mock_config_entry.entry_id] = (
        mock_runtime_data
    )

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")
    handler.context = {"source": "user"}  # Required for async_create_entry

    # Mock the _get_entry method to return our mock config entry
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Test successful route creation with via and time
    result = await handler.async_step_user(
        user_input={
            "name": "Complex Route",
            "from": "AMS",
            "to": "GVC",
            "via": "UTR",
            "time": "08:30:00",
        }
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Complex Route"
    assert result.get("data") == {
        "name": "Complex Route",
        "from": "AMS",
        "to": "GVC",
        "via": "UTR",
        "time": "08:30:00",
    }


async def test_subentry_flow_validation_errors(hass: HomeAssistant) -> None:
    """Test validation errors in subentry flow."""
    # Create a mock config entry with stations data
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Mock runtime data with stations
    mock_coordinator = MagicMock()
    mock_runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=[
            {"code": "AMS", "name": "Amsterdam Centraal"},
            {"code": "UTR", "name": "Utrecht Centraal"},
        ],
        stations_updated="2024-01-01T00:00:00Z",
    )

    # Set runtime_data directly on the mock config entry
    mock_config_entry.runtime_data = mock_runtime_data

    # Add to hass data
    hass.data.setdefault("nederlandse_spoorwegen", {})[mock_config_entry.entry_id] = (
        mock_runtime_data
    )

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")

    # Mock the _get_entry method to return our mock config entry
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Test missing fields
    result = await handler.async_step_user(
        user_input={
            "name": "",
            "from": "",
            "to": "",
        }
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {"base": "missing_fields"}

    # Test same from/to stations
    result = await handler.async_step_user(
        user_input={
            "name": "Test Route",
            "from": "AMS",
            "to": "AMS",
        }
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {"base": "same_station"}

    # Test invalid station codes (not in available stations)
    result = await handler.async_step_user(
        user_input={
            "name": "Test Route",
            "from": "INVALID",
            "to": "UTR",
        }
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {"from": "invalid_station"}


async def test_subentry_flow_no_stations_available(hass: HomeAssistant) -> None:
    """Test subentry flow when no stations are available."""
    # Create a mock config entry without stations data
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Mock runtime data with no stations
    mock_coordinator = MagicMock()
    mock_runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=None,
        stations_updated=None,
    )

    # Set runtime_data directly on the mock config entry
    mock_config_entry.runtime_data = mock_runtime_data

    # Add to hass data
    hass.data.setdefault("nederlandse_spoorwegen", {})[mock_config_entry.entry_id] = (
        mock_runtime_data
    )

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")

    # Mock the _get_entry method to return our mock config entry
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Test form creation when no stations available
    result = await handler.async_step_user()

    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {"base": "no_stations_available"}


async def test_subentry_flow_reconfigure_mode(hass: HomeAssistant) -> None:
    """Test subentry flow in reconfigure mode."""
    # Create a mock config entry with stations data
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Mock runtime data with stations
    mock_coordinator = MagicMock()
    mock_runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=[
            {"code": "AMS", "name": "Amsterdam Centraal"},
            {"code": "UTR", "name": "Utrecht Centraal"},
        ],
        stations_updated="2024-01-01T00:00:00Z",
    )

    # Set runtime_data directly on the mock config entry
    mock_config_entry.runtime_data = mock_runtime_data

    # Add to hass data
    hass.data.setdefault("nederlandse_spoorwegen", {})[mock_config_entry.entry_id] = (
        mock_runtime_data
    )

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")
    handler.context = {"source": "user"}  # Required for async_create_entry

    # Mock the _get_entry method
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Test successful reconfigure by calling async_step_reconfigure directly
    result = await handler.async_step_reconfigure(
        user_input={
            "name": "Updated Route",
            "from": "UTR",
            "to": "AMS",
            "via": "",
            "time": "10:00:00",
        }
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Updated Route"
    assert result.get("data") == {
        "name": "Updated Route",
        "from": "UTR",
        "to": "AMS",
        "time": "10:00:00",
    }


async def test_subentry_flow_reconfigure_with_existing_data(
    hass: HomeAssistant,
) -> None:
    """Test subentry flow reconfigure mode with existing route data."""
    # Create a mock config entry with stations data
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Mock runtime data with stations
    mock_coordinator = MagicMock()
    mock_runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=[
            {"code": "AMS", "name": "Amsterdam Centraal"},
            {"code": "UTR", "name": "Utrecht Centraal"},
            {"code": "GVC", "name": "Den Haag Centraal"},
        ],
        stations_updated="2024-01-01T00:00:00Z",
    )

    # Set runtime_data directly on the mock config entry
    mock_config_entry.runtime_data = mock_runtime_data

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")
    handler.context = {"source": "reconfigure"}  # Use reconfigure source

    # Mock the _get_entry method
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Mock the _get_reconfigure_subentry method to return existing route data
    existing_subentry = MagicMock()
    existing_subentry.data = {
        "name": "Existing Route",
        "from": "AMS",
        "to": "UTR",
        "via": "",
        "time": "09:00",
    }
    handler._get_reconfigure_subentry = MagicMock(return_value=existing_subentry)

    # Test showing the form with existing data
    result = await handler.async_step_reconfigure()

    assert result.get("type") == "form"
    assert result.get("step_id") == "user"
    assert "data_schema" in result

    # Verify form was created successfully (specific schema validation would require more complex mocking)
    data_schema = result["data_schema"]
    assert data_schema is not None


async def test_subentry_flow_invalid_via_station(hass: HomeAssistant) -> None:
    """Test validation of invalid via station in subentry flow."""
    # Create a mock config entry with stations data
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Mock runtime data with limited stations
    mock_coordinator = MagicMock()
    mock_runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=[
            {"code": "AMS", "name": "Amsterdam Centraal"},
            {"code": "UTR", "name": "Utrecht Centraal"},
        ],
        stations_updated="2024-01-01T00:00:00Z",
    )

    # Set runtime_data directly on the mock config entry
    mock_config_entry.runtime_data = mock_runtime_data

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")
    handler.context = {"source": "user"}

    # Mock the _get_entry method
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Test with invalid via station
    result = await handler.async_step_user(
        user_input={
            "name": "Test Route",
            "from": "AMS",
            "to": "UTR",
            "via": "INVALID_STATION",
            "time": "",
        }
    )

    assert result.get("type") == "form"
    assert result.get("errors") == {"via": "invalid_station"}


async def test_subentry_flow_multiple_validation_errors(hass: HomeAssistant) -> None:
    """Test multiple validation errors in subentry flow."""
    # Create a mock config entry with stations data
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Mock runtime data with stations
    mock_coordinator = MagicMock()
    mock_runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=[
            {"code": "AMS", "name": "Amsterdam Centraal"},
            {"code": "UTR", "name": "Utrecht Centraal"},
        ],
        stations_updated="2024-01-01T00:00:00Z",
    )

    # Set runtime_data directly on the mock config entry
    mock_config_entry.runtime_data = mock_runtime_data

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")
    handler.context = {"source": "user"}

    # Mock the _get_entry method
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Test with multiple invalid stations
    result = await handler.async_step_user(
        user_input={
            "name": "Test Route",
            "from": "INVALID_FROM",
            "to": "INVALID_TO",
            "via": "",
            "time": "",
        }
    )

    assert result.get("type") == "form"
    errors = result.get("errors", {})
    assert errors is not None
    assert "from" in errors
    assert "to" in errors
    assert errors["from"] == "invalid_station"
    assert errors["to"] == "invalid_station"


async def test_subentry_flow_station_options_formatting(hass: HomeAssistant) -> None:
    """Test station options are properly formatted for dropdowns."""
    # Create a mock config entry with stations data
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Mock runtime data with different station formats
    mock_coordinator = MagicMock()
    mock_runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=[
            # Station with proper name and code attributes
            type("Station", (), {"code": "AMS", "name": "Amsterdam Centraal"})(),
            # Station as dict format
            {"code": "UTR", "name": "Utrecht Centraal"},
            # Station with minimal data
            {"code": "GVC", "name": "Den Haag Centraal"},
            # Station as string in "CODE Name" format (real API format)
            "AC Abcoude",
            "RTD Rotterdam Centraal",
            # Station with __str__ that includes class name (the problematic format)
            type("Station", (), {"__str__": lambda self: "<Station> ZL Zwolle"})(),
        ],
        stations_updated="2024-01-01T00:00:00Z",
    )

    # Set runtime_data directly on the mock config entry
    mock_config_entry.runtime_data = mock_runtime_data

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")
    handler.context = {"source": "user"}

    # Mock the _get_entry method
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Get station options
    station_options = await handler._get_station_options()

    # Verify options are properly formatted
    assert len(station_options) == 6  # Updated count

    # Check specific formats
    expected_labels = [
        "Abcoude",
        "Amsterdam Centraal",
        "Den Haag Centraal",
        "Rotterdam Centraal",
        "Utrecht Centraal",
        "Zwolle",
    ]

    actual_labels = [opt["label"] for opt in station_options]

    # Should be sorted by label
    assert actual_labels == sorted(expected_labels)

    # Values should correspond correctly
    for option in station_options:
        assert isinstance(option, dict)
        assert "value" in option
        assert "label" in option

        # Specific format checks
        if option["label"] == "Abcoude":
            assert option["value"] == "AC"
        elif option["label"] == "Rotterdam Centraal":
            assert option["value"] == "RTD"
        elif option["label"] == "Zwolle":
            assert option["value"] == "ZL"


async def test_subentry_flow_exception_handling(hass: HomeAssistant) -> None:
    """Test exception handling in subentry flow."""
    # Create a mock config entry with no runtime data
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")
    handler.context = {"source": "user"}

    # Mock the _get_entry method to return the config entry
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Mock _ensure_stations_available to raise an exception
    handler._ensure_stations_available = MagicMock(
        side_effect=Exception("Test exception")
    )

    # Test exception is handled gracefully
    result = await handler.async_step_user(
        user_input={
            "name": "Test Route",
            "from": "AMS",
            "to": "UTR",
        }
    )

    assert result.get("type") == "form"
    assert result.get("errors") == {"base": "unknown"}


async def test_subentry_flow_empty_station_list(hass: HomeAssistant) -> None:
    """Test subentry flow behavior with empty station list."""
    # Create a mock config entry with empty stations
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Mock runtime data with empty stations list
    mock_coordinator = MagicMock()
    mock_runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=[],  # Empty list
        stations_updated="2024-01-01T00:00:00Z",
    )

    # Set runtime_data directly on the mock config entry
    mock_config_entry.runtime_data = mock_runtime_data

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")
    handler.context = {"source": "user"}

    # Mock the _get_entry method
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Test form creation when stations list is empty
    result = await handler.async_step_user()

    assert result.get("type") == "form"
    assert result.get("errors") == {"base": "no_stations_available"}


async def test_subentry_flow_case_insensitive_station_codes(
    hass: HomeAssistant,
) -> None:
    """Test that station codes are stored in uppercase regardless of input."""
    # Create a mock config entry with stations data
    mock_config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={CONF_API_KEY: API_KEY},
    )

    # Mock runtime data with lowercase station codes
    mock_coordinator = MagicMock()
    mock_runtime_data = NSRuntimeData(
        coordinator=mock_coordinator,
        stations=[
            {"code": "ams", "name": "Amsterdam Centraal"},
            {"code": "utr", "name": "Utrecht Centraal"},
            {"code": "gvc", "name": "Den Haag Centraal"},
        ],
        stations_updated="2024-01-01T00:00:00Z",
    )

    # Set runtime_data directly on the mock config entry
    mock_config_entry.runtime_data = mock_runtime_data

    # Create a subentry flow handler instance
    handler = config_flow.RouteSubentryFlowHandler()
    handler.hass = hass
    handler.handler = (mock_config_entry.entry_id, "route")
    handler.context = {"source": "user"}

    # Mock the _get_entry method
    handler._get_entry = MagicMock(return_value=mock_config_entry)

    # Test with lowercase input - should be stored as uppercase
    result = await handler.async_step_user(
        user_input={
            "name": "Test Route",
            "from": "ams",  # lowercase input
            "to": "utr",  # lowercase input
            "via": "gvc",  # lowercase input
            "time": "10:30:00",
        }
    )

    assert result.get("type") == "create_entry"
    assert result.get("title") == "Test Route"

    # Verify data is stored in uppercase
    data = result.get("data", {})
    assert data.get("from") == "AMS"
    assert data.get("to") == "UTR"
    assert data.get("via") == "GVC"
    assert data.get("time") == "10:30:00"
