"""Test the Västtrafik config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.vasttrafik.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryData
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
    return (
        [
            {"value": "Central Station", "label": "Central Station (12345)"},
            {"value": "Götaplatsen", "label": "Götaplatsen (54321)"},
        ],
        None,
    )


async def test_user_setup_first_time(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test setting up credentials for the first time (no existing integration)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.vasttrafik.config_flow.validate_api_credentials",
        return_value=None,
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
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that only one main integration instance is allowed."""
    # Create main integration entry
    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "test-key", "secret": "test-secret"},
        unique_id="vasttrafik",
    )
    main_entry.add_to_hass(hass)

    # Try to set up another instance - should be aborted
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth during setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vasttrafik.config_flow.validate_api_credentials",
        return_value={"base": "invalid_auth"},
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


async def test_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error during setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vasttrafik.config_flow.validate_api_credentials",
        return_value={"base": "cannot_connect"},
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


async def test_subentry_departure_board(
    hass: HomeAssistant, mock_setup_entry, mock_search_stations
) -> None:
    """Test setting up a departure board subentry."""
    # Create main integration entry first
    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "test-key", "secret": "test-secret"},
        unique_id="vasttrafik",
    )
    main_entry.add_to_hass(hass)

    # Set up the runtime_data
    main_entry.runtime_data = MagicMock()

    # Initiate subentry flow using the correct API
    result = await hass.config_entries.subentries.async_init(
        (main_entry.entry_id, "departure_board"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Mock search stations
    with patch(
        "homeassistant.components.vasttrafik.config_flow.search_stations",
        return_value=mock_search_stations,
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"search_query": "Central"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "select_station"

    # Select a station
    result3 = await hass.config_entries.subentries.async_configure(
        result2["flow_id"],
        {"station": "Central Station"},
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "configure"

    # Configure departure sensor
    result4 = await hass.config_entries.subentries.async_configure(
        result3["flow_id"],
        {
            "name": "Central Departures",
            "lines": ["1", "2", "55"],
            "tracks": ["A", "B"],
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
    }


async def test_subentry_no_stations_found(hass: HomeAssistant) -> None:
    """Test subentry search with no results."""
    # Create main integration entry
    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "test-key", "secret": "test-secret"},
        unique_id="vasttrafik",
    )
    main_entry.add_to_hass(hass)

    # Set up the runtime_data
    main_entry.runtime_data = MagicMock()

    result = await hass.config_entries.subentries.async_init(
        (main_entry.entry_id, "departure_board"),
        context={"source": config_entries.SOURCE_USER},
    )

    # Mock search stations returning no results
    with patch(
        "homeassistant.components.vasttrafik.config_flow.search_stations",
        return_value=([], "no_stations_found"),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"search_query": "NonExistentStation"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "no_stations_found"}


# Duplicate prevention test removed - feature not implemented yet


async def test_main_integration_reconfigure(hass: HomeAssistant) -> None:
    """Test reconfiguring the main integration API credentials."""
    # Create main integration entry
    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "test-key", "secret": "test-secret"},
        unique_id="vasttrafik",
    )
    main_entry.add_to_hass(hass)

    # Start reconfigure flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": main_entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Form should be displayed for reconfiguration
    assert result["step_id"] == "reconfigure"

    # Configure new credentials
    with patch(
        "homeassistant.components.vasttrafik.config_flow.validate_api_credentials",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "key": "new-test-key",
                "secret": "new-test-secret",
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"


async def test_subentry_reconfigure(hass: HomeAssistant) -> None:
    """Test reconfiguring a departure board subentry."""
    # Create subentry data
    subentry_data = ConfigSubentryData(
        data={
            "from": "Central Station",
            "name": "Central Departures",
            "lines": ["1", "2"],
            "tracks": ["A"],
            "delay": 5,
        },
        subentry_type="departure_board",
        title="Departure: Central Departures",
        unique_id=None,
    )

    # Create main integration entry with subentry
    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "test-key", "secret": "test-secret"},
        unique_id="vasttrafik",
        subentries_data=[subentry_data],
    )
    main_entry.add_to_hass(hass)

    # Set up runtime data
    main_entry.runtime_data = MagicMock()

    # Get the created subentry
    subentry = list(main_entry.subentries.values())[0]

    # Start reconfigure flow using the correct API
    result = await main_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Configure new options using subentries API
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Updated Central Departures",
            "lines": ["1", "2", "55"],
            "tracks": ["A", "B", "C"],
            "delay": 10,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"


async def test_import_success_no_departures(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test successful import flow from YAML with no departures."""
    with patch(
        "homeassistant.components.vasttrafik.config_flow.validate_api_credentials",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"key": "test-key", "secret": "test-secret"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Västtrafik"
    assert result["data"] == {"key": "test-key", "secret": "test-secret"}
    assert not result["result"].subentries


async def test_import_with_departures(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test import flow with departures from YAML configuration."""
    with patch(
        "homeassistant.components.vasttrafik.config_flow.validate_api_credentials",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "key": "test-key",
                "secret": "test-secret",
                "departures": [
                    {
                        "from": "Centralstationen",
                        "name": "Central Departures",
                        "heading": "Angered",
                        "lines": ["1", "2"],
                        "delay": 5,
                    },
                    {
                        "from": "Götaplatsen",
                        "name": "Götaplatsen to City",
                        "tracks": ["A", "B"],
                        "delay": 0,
                    },
                ],
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Västtrafik"
    assert result["data"] == {"key": "test-key", "secret": "test-secret"}
    assert len(result["result"].subentries) == 2

    subentries = list(result["result"].subentries.values())

    assert subentries[0].title == "Central Departures"
    assert subentries[0].subentry_type == "departure_board"
    assert subentries[0].data == {
        "from": "Centralstationen",
        "name": "Central Departures",
        "heading": "Angered",
        "lines": ["1", "2"],
        "tracks": [],
        "delay": 5,
    }

    assert subentries[1].title == "Götaplatsen to City"
    assert subentries[1].subentry_type == "departure_board"
    assert subentries[1].data == {
        "from": "Götaplatsen",
        "name": "Götaplatsen to City",
        "heading": "",
        "lines": [],
        "tracks": ["A", "B"],
        "delay": 0,
    }


async def test_import_already_configured(hass: HomeAssistant) -> None:
    """Test import flow when integration is already configured."""
    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "test-key", "secret": "test-secret"},
    )
    main_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.vasttrafik.config_flow.validate_api_credentials",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"key": "test-key", "secret": "test-secret"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.parametrize(
    ("error_return", "expected_reason"),
    [
        ({"base": "invalid_auth"}, "invalid_auth"),
        ({"base": "cannot_connect"}, "cannot_connect"),
        ({"base": "unknown"}, "unknown"),
    ],
)
async def test_import_exceptions(
    hass: HomeAssistant, error_return: dict[str, str], expected_reason: str
) -> None:
    """Test import flow handling different errors."""
    with patch(
        "homeassistant.components.vasttrafik.config_flow.validate_api_credentials",
        return_value=error_return,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"key": "test-key", "secret": "test-secret"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
