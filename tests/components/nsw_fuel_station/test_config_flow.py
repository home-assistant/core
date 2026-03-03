"""Tests for NSW Fuel Check config flow."""

from unittest.mock import AsyncMock, patch

from nsw_tas_fuel import NSWFuelApiClientAuthError, NSWFuelApiClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.nsw_fuel_station.const import DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    CLIENT_ID,
    CLIENT_SECRET,
    HOBART_LAT,
    HOBART_LNG,
    HOME_LAT,
    HOME_LNG,
    STATION_NSW_A,
    STATION_NSW_B,
    STATION_NSW_C,
    STATION_TAS_D,
    STATION_TAS_E,
)

from tests.common import MockConfigEntry

NSW_FUEL_API_DEFINITION = (
    "homeassistant.components.nsw_fuel_station.config_flow.NSWFuelApiClient"
)


@pytest.mark.parametrize(
    ("latitude", "longitude", "expected_state", "station_code"),
    [
        (HOME_LAT, HOME_LNG, "NSW", STATION_NSW_A),
        (HOBART_LAT, HOBART_LNG, "TAS", STATION_TAS_D),
        (HOBART_LAT, HOBART_LNG, "TAS", STATION_TAS_E),
    ],
    ids=["nsw", "tas-d", "tas-e"],
)
async def test_successful_config_flow(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_env: dict[str, str],
    latitude: float,
    longitude: float,
    expected_state: str,
    station_code: int,
) -> None:
    """Test successful config flow - NSW and TAS variants."""
    hass.config.latitude = latitude
    hass.config.longitude = longitude
    hass.config.time_zone = "Australia/Sydney"

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=mock_api_client,
        ),
    ):
        # Step 1: Start flow - show credentials form
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Step 2: Submit credentials
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_select"

        # Step 3: Select station
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": [str(station_code)]},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "NSW Fuel Check"

        # Verify data structure
        data = result["data"]
        assert "nicknames" in data
        assert "Home" in data["nicknames"]
        home = data["nicknames"]["Home"]
        assert len(home["stations"]) == 1
        assert home["stations"][0]["station_code"] == station_code
        assert home["stations"][0]["au_state"] == expected_state

        # Verify location (latitude/longitude) is stored with the nickname
        assert "location" in home
        assert "latitude" in home["location"]
        assert "longitude" in home["location"]
        assert home["location"]["latitude"] == latitude
        assert home["location"]["longitude"] == longitude

        # Verify fuel type handling: E10 added automatically for NSW, not for TAS
        fuel_types = home["stations"][0].get("fuel_types", [])
        assert "U91" in fuel_types
        if expected_state == "NSW":
            # NSW: E10 should be added automatically with U91
            assert "E10" in fuel_types
        else:
            # TAS: E10 should NOT be added
            assert "E10" not in fuel_types

        await hass.async_block_till_done()
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1


async def test_no_station_selected_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_env: dict[str, str],
) -> None:
    """Test error when user doesn't select any station."""
    hass.config.latitude = HOME_LAT
    hass.config.longitude = HOME_LNG

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=mock_api_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        # Submit empty station list
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": []},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_select"
        assert "no_stations" in result["errors"]["base"]


async def test_no_available_stations_abort(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_env: dict[str, str],
) -> None:
    """Test flow aborts when all stations already configured."""
    hass.config.latitude = HOME_LAT
    hass.config.longitude = HOME_LNG

    # Add existing entry with all stations
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NSW Fuel",
        data={
            "nicknames": {
                "Home": {
                    "stations": [
                        {"station_code": STATION_NSW_A, "au_state": "NSW"},
                        {"station_code": STATION_NSW_B, "au_state": "NSW"},
                        {"station_code": STATION_NSW_C, "au_state": "NSW"},
                    ]
                }
            }
        },
        source=config_entries.SOURCE_USER,
        version=1,
    )
    existing_entry.add_to_hass(hass)

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=mock_api_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        # Should abort - no available stations
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_available_stations"


async def test_add_station_to_existing_nickname(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_env: dict[str, str],
) -> None:
    """Test adding second station to existing nickname."""
    hass.config.latitude = HOME_LAT
    hass.config.longitude = HOME_LNG

    # Add existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NSW Fuel",
        data={
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
            "nicknames": {
                "Home": {
                    "stations": [
                        {
                            "station_code": STATION_NSW_A,
                            "au_state": "NSW",
                            "fuel_types": ["U91"],
                        }
                    ]
                }
            },
        },
        source=config_entries.SOURCE_USER,
        version=1,
    )
    existing_entry.add_to_hass(hass)

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=mock_api_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        # Station A should be filtered out, only B available
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": [str(STATION_NSW_B)]},
        )

        # Updating existing entry returns ABORT with reason "updated_existing"
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "updated_existing"

        # Verify the entry was updated with both stations
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        home = entries[0].data["nicknames"]["Home"]
        station_codes = [s["station_code"] for s in home["stations"]]
        assert STATION_NSW_A in station_codes
        assert STATION_NSW_B in station_codes


async def test_invalid_credentials(
    hass: HomeAssistant,
    mock_env: dict[str, str],
) -> None:
    """Test invalid API credentials."""
    hass.config.latitude = HOME_LAT
    hass.config.longitude = HOME_LNG

    bad_client = AsyncMock()
    bad_client.get_fuel_prices_within_radius = AsyncMock(
        side_effect=NSWFuelApiClientAuthError("Invalid credentials")
    )

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=bad_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": "bad", "client_secret": "bad"},
        )

        # Should show error on user form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]


async def test_timeout_error_on_station_fetch(
    hass: HomeAssistant,
    mock_env: dict[str, str],
) -> None:
    """Test timeout (408) error handling when fetching stations."""
    hass.config.latitude = HOME_LAT
    hass.config.longitude = HOME_LNG

    timeout_client = AsyncMock()
    timeout_client.get_fuel_prices_within_radius = AsyncMock(
        side_effect=NSWFuelApiClientError("Request timeout (408)")
    )

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=timeout_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        # Should show connection error on user form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert "base" in result["errors"]
        assert result["errors"]["base"] == "connection"


@pytest.mark.parametrize(
    "error_message",
    [
        "Request timeout (408)",
        "Bad request (400)",
        "Internal server error (500)",
    ],
    ids=[
        "408-timeout",
        "400-bad-request",
        "500-server-error",
    ],
)
async def test_api_connection_errors_on_station_fetch(
    hass: HomeAssistant,
    mock_env: dict[str, str],
    error_message: str,
) -> None:
    """Test various API connection errors (4xx and 5xx) when fetching stations."""
    hass.config.latitude = HOME_LAT
    hass.config.longitude = HOME_LNG

    error_client = AsyncMock()
    error_client.get_fuel_prices_within_radius = AsyncMock(
        side_effect=NSWFuelApiClientError(error_message)
    )

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=error_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        # All API errors should show connection error on user form


async def test_invalid_location_goes_to_advanced(
    hass: HomeAssistant,
    mock_env: dict[str, str],
) -> None:
    """Test invalid location (outside service area) routes to advanced options."""
    # Set location outside Australia (South Pole)
    hass.config.latitude = -90.0
    hass.config.longitude = 0.0

    mock_client = AsyncMock()

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=mock_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        # Should go to advanced options due to invalid location
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "advanced_options"


async def test_invalid_location_in_advanced_options(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_env: dict[str, str],
) -> None:
    """Test invalid location handling when submitting advanced options form."""
    hass.config.latitude = HOME_LAT
    hass.config.longitude = HOME_LNG

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=mock_api_client,
        ),
    ):
        # Start with valid location to get to station_select step
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_select"

        # Select advanced options
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": ["__advanced__"]},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "advanced_options"

        # Submit advanced options with INVALID location (South Pole - outside NSW/TAS)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "nickname": "Work",
                "location": {"latitude": -90.0, "longitude": 0.0},
                "fuel_type": "U91",
            },
        )

        # Should show error and remain on advanced_options
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "advanced_options"
        assert "base" in result["errors"]
        assert result["errors"]["base"] == "invalid_coordinates"


async def test_invalid_nickname_in_advanced_options(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_env: dict[str, str],
) -> None:
    """Test invalid nickname handling in advanced options form."""
    hass.config.latitude = HOME_LAT
    hass.config.longitude = HOME_LNG

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=mock_api_client,
        ),
    ):
        # Start with valid location to get to station_select step
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_select"

        # Select advanced options
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": ["__advanced__"]},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "advanced_options"

        # Submit with invalid nickname containing spaces and special characters
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "nickname": "My Work!",  # Invalid: contains space and exclamation mark
                "location": {"latitude": HOME_LAT, "longitude": HOME_LNG},
                "fuel_type": "U91",
            },
        )

        # Should show error and remain on advanced_options
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "advanced_options"
        assert "nickname" in result["errors"]
        assert result["errors"]["nickname"] == "invalid_nickname"

        # Test empty nickname as well
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "nickname": "",  # Invalid: empty
                "location": {"latitude": HOME_LAT, "longitude": HOME_LNG},
                "fuel_type": "U91",
            },
        )

        # Should show error again
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "advanced_options"
        assert "nickname" in result["errors"]
        assert result["errors"]["nickname"] == "invalid_nickname"

        # Test valid nickname with hyphen and underscore
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "nickname": "Work-Home_2",  # Valid: hyphen and underscore OK
                "location": {"latitude": HOME_LAT, "longitude": HOME_LNG},
                "fuel_type": "U91",
            },
        )

        # Should proceed to station_select (no nickname error)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_select"
        assert "nickname" not in result.get("errors", {})


async def test_add_fuel_type_to_existing_station_via_advanced(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_env: dict[str, str],
) -> None:
    """Test adding a new fuel type (DL) to an existing station via advanced options."""
    hass.config.latitude = HOME_LAT
    hass.config.longitude = HOME_LNG

    # Add existing entry with station A having only U91 fuel type
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NSW Fuel Check",
        data={
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
            "nicknames": {
                "Home": {
                    "stations": [
                        {
                            "station_code": STATION_NSW_A,
                            "au_state": "NSW",
                            "station_name": "Ampol Foodary Batemans Bay",
                            "fuel_types": ["U91"],
                        }
                    ]
                }
            },
        },
        source=config_entries.SOURCE_USER,
        version=1,
    )
    existing_entry.add_to_hass(hass)

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=mock_api_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        # Access advanced options
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": ["__advanced__"]},
        )

        # Should be in advanced options form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "advanced_options"

        # Configure advanced options: nickname and fuel type
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "nickname": "Home",
                "fuel_type": "DL",
            },
        )

        # Advanced options transitions to station_select
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_select"

        # In advanced path, can select existing station A (NOT filtered out)
        # This allows adding DL fuel type to existing station
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": [str(STATION_NSW_A)]},
        )

        # Should update existing entry
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "updated_existing"

        # Verify the entry was updated with DL fuel type added to station A
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        home = entries[0].data["nicknames"]["Home"]
        assert len(home["stations"]) == 1
        station = home["stations"][0]
        assert station["station_code"] == STATION_NSW_A
        assert "U91" in station["fuel_types"]
        assert "DL" in station["fuel_types"]
        # Fuel types should be sorted
        assert sorted(station["fuel_types"]) == ["DL", "U91"]


async def test_add_multiple_nicknames(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_env: dict[str, str],
) -> None:
    """Test creating multiple config entries with different nicknames."""
    hass.config.latitude = HOME_LAT
    hass.config.longitude = HOME_LNG

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=mock_api_client,
        ),
    ):
        # Create FIRST config entry with "Home" nickname (default)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": [str(STATION_NSW_A)]},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        first_entry = entries[0]
        assert "Home" in first_entry.data["nicknames"]

        # Create SECOND config entry with "Work" nickname via advanced options
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        # Go to advanced path to set custom nickname
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": ["__advanced__"]},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "advanced_options"

        # Set nickname to "Work" instead of default "Home"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "nickname": "Work",
                "fuel_type": "U91",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_select"

        # Select station B for Work nickname
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": [str(STATION_NSW_B)]},
        )

        # Should create new entry (not update) since "Work" is a new nickname
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

        # Verify we now have TWO separate config entries
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 2

        # Find each entry by nickname
        nicknames = {}
        for entry in entries:
            entry_nicknames = list(entry.data.get("nicknames", {}).keys())
            for nick in entry_nicknames:
                nicknames[nick] = entry

        # Both nicknames should exist
        assert "Home" in nicknames
        assert "Work" in nicknames

        # Home entry should have station A
        home_entry = nicknames["Home"]
        home_stations = [
            s["station_code"] for s in home_entry.data["nicknames"]["Home"]["stations"]
        ]
        assert STATION_NSW_A in home_stations

        # Work entry should have station B
        work_entry = nicknames["Work"]
        work_stations = [
            s["station_code"] for s in work_entry.data["nicknames"]["Work"]["stations"]
        ]
        assert STATION_NSW_B in work_stations


async def test_duplicate_fuel_type_in_advanced_path(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_env: dict[str, str],
) -> None:
    """Test error when trying to add duplicate fuel type to a station."""
    hass.config.latitude = HOME_LAT
    hass.config.longitude = HOME_LNG

    # Add existing entry with station A having DL (Diesel) - not U91
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NSW Fuel Check",
        data={
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
            "nicknames": {
                "Home": {
                    "location": {"latitude": HOME_LAT, "longitude": HOME_LNG},
                    "stations": [
                        {
                            "station_code": STATION_NSW_A,
                            "au_state": "NSW",
                            "station_name": "Ampol Foodary Ampol Foodary Batemans Bay",
                            "fuel_types": ["U91", "DL"],  # Has both U91 and DL
                        }
                    ],
                }
            },
        },
        source=config_entries.SOURCE_USER,
        version=1,
    )
    existing_entry.add_to_hass(hass)

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=mock_api_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        # Go to advanced options
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": ["__advanced__"]},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "advanced_options"

        # Configure advanced options - add DL fuel type to existing "Home" nickname
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "nickname": "Home",  # EXISTING nickname
                "fuel_type": "DL",  # Non-U91 fuel type that already exists on station A
            },
        )

        # Should go to station_select
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_select"

        # Try to select station A with DL - this already exists in Home!
        # This should trigger sensor_exists error (line 415)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": [str(STATION_NSW_A)]},
        )

        # Should show sensor_exists error and stay on station_select
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_select"
        assert result["errors"]["base"] == "sensor_exists"


async def test_location_outside_nsw_tas_bounds(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_env: dict[str, str],
) -> None:
    """Test error when location is outside NSW/TAS geographic bounds."""
    hass.config.latitude = HOME_LAT
    hass.config.longitude = HOME_LNG

    with (
        patch.dict("os.environ", mock_env),
        patch(
            NSW_FUEL_API_DEFINITION,
            return_value=mock_api_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

        # Go to advanced options
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_station_codes": ["__advanced__"]},
        )

        # Test with latitude north of NSW/TAS bounds (> -28.99608)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "nickname": "OutOfBounds",
                "location": {"latitude": -20.0, "longitude": 150.0},  # Too far north
                "fuel_type": "U91",
            },
        )

        # Should show invalid_coordinates error and stay on advanced_options
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "advanced_options"
        assert result["errors"]["base"] == "invalid_coordinates"

        # Test with longitude west of NSW/TAS bounds (< 141.00180)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "nickname": "OutOfBounds",
                "location": {"latitude": -35.0, "longitude": 130.0},  # Too far west
                "fuel_type": "U91",
            },
        )

        # Should show invalid_coordinates error
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "advanced_options"
        assert result["errors"]["base"] == "invalid_coordinates"
