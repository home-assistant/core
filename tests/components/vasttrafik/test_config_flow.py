"""Test the Västtrafik config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.vasttrafik.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> None:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.vasttrafik.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_search_stations():
    """Mock station search results."""
    return ([
        {"value": "Central Station", "label": "Central Station (12345)"},
        {"value": "Götaplatsen", "label": "Götaplatsen (54321)"}
    ], None)


async def test_credentials_setup_first_time(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test setting up credentials for the first time (no existing main integration)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.vasttrafik.config_flow.validate_input",
        return_value={"title": "Västtrafik"},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "key": "test-key",
                "secret": "test-secret",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Västtrafik"
    assert result2["data"] == {
        "key": "test-key",
        "secret": "test-secret",
        "is_departure_board": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_departure_board_setup_with_existing_main(hass: HomeAssistant, mock_setup_entry, mock_search_stations) -> None:
    """Test setting up departure board when main integration exists."""
    # Create main integration entry
    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "test-key", "secret": "test-secret", "is_departure_board": False},
        unique_id="vasttrafik_main",
    )
    main_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "departure_board"

    # Mock search stations
    with patch(
        "homeassistant.components.vasttrafik.config_flow.search_stations",
        return_value=mock_search_stations,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"search_query": "Central"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "select_departure_station"

    # Select a station
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {"station": "Central Station"},
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "configure_departure_sensor"

    # Configure departure sensor
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {
            "name": "Central Departures",
            "lines": "1, 2, 55",
            "tracks": "A, B",
            "delay": 5,
        },
    )

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "Departure: Central Departures"
    assert result4["data"] == {
        "from": "Central Station",
        "name": "Central Departures",
        "heading": "",
        "lines": ["1", "2", "55"],
        "tracks": ["A", "B"],
        "delay": 5,
        "is_departure_board": True,
    }


async def test_credentials_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth during credentials setup."""
    from homeassistant.components.vasttrafik.config_flow import InvalidAuth
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vasttrafik.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "key": "test-key",
                "secret": "test-secret",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_credentials_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error during credentials setup."""
    from homeassistant.components.vasttrafik.config_flow import CannotConnect
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vasttrafik.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "key": "test-key",
                "secret": "test-secret",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_departure_board_search_too_short(hass: HomeAssistant) -> None:
    """Test departure board search with query too short."""
    # Create main integration entry
    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "test-key", "secret": "test-secret", "is_departure_board": False},
        unique_id="vasttrafik_main",
    )
    main_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Test with empty query (schema validation will fail)
    from homeassistant.data_entry_flow import InvalidData
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"search_query": "C"},  # Too short - will fail schema validation
        )


async def test_departure_board_no_stations_found(hass: HomeAssistant) -> None:
    """Test departure board search with no results."""
    # Create main integration entry
    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "test-key", "secret": "test-secret", "is_departure_board": False},
        unique_id="vasttrafik_main",
    )
    main_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock search stations returning no results
    with patch(
        "homeassistant.components.vasttrafik.config_flow.search_stations",
        return_value=([], "no_stations_found"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"search_query": "NonExistentStation"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "no_stations_found"}


async def test_departure_board_duplicate_prevention(hass: HomeAssistant, mock_search_stations) -> None:
    """Test preventing duplicate departure boards."""
    # Create main integration entry
    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "test-key", "secret": "test-secret", "is_departure_board": False},
        unique_id="vasttrafik_main",
    )
    main_entry.add_to_hass(hass)
    
    # Create existing departure board
    existing_departure = MockConfigEntry(
        domain=DOMAIN,
        data={"from": "Central Station", "is_departure_board": True},
        unique_id="vasttrafik_departure_central_station",
    )
    existing_departure.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock search stations
    with patch(
        "homeassistant.components.vasttrafik.config_flow.search_stations",
        return_value=mock_search_stations,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"search_query": "Central"},
        )

    # Select the same station
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {"station": "Central Station"},
    )

    # Try to configure - should be aborted due to duplicate
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {"name": "Central Departures"},
    )

    assert result4["type"] is FlowResultType.ABORT
    assert result4["reason"] == "already_configured"


async def test_options_flow_departure_board(hass: HomeAssistant) -> None:
    """Test options flow for departure board."""
    # Create a departure board entry
    departure_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "from": "Central Station",
            "name": "Central Departures", 
            "lines": ["1", "2"],
            "tracks": ["A"],
            "delay": 5,
            "is_departure_board": True,
        },
        unique_id="vasttrafik_departure_central_station",
    )
    departure_entry.add_to_hass(hass)

    # Start options flow
    result = await hass.config_entries.options.async_init(departure_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Configure new options
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Updated Central Departures",
            "lines": "1, 2, 55",
            "tracks": "A, B, C",
            "delay": 10,
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    
    # Verify the config entry was updated
    assert departure_entry.data["name"] == "Updated Central Departures"
    assert departure_entry.data["lines"] == ["1", "2", "55"]
    assert departure_entry.data["tracks"] == ["A", "B", "C"]
    assert departure_entry.data["delay"] == 10


async def test_options_flow_main_integration_not_configurable(hass: HomeAssistant) -> None:
    """Test that main integration entries cannot use options flow."""
    # Create main integration entry
    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "test-key", "secret": "test-secret", "is_departure_board": False},
        unique_id="vasttrafik_main",
    )
    main_entry.add_to_hass(hass)

    # Try to start options flow - should be aborted
    result = await hass.config_entries.options.async_init(main_entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_configurable"