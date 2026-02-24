"""Test the dk_fuelprices config flow."""

from unittest.mock import AsyncMock, Mock

from aiohttp import ClientResponseError

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_API_KEY, TEST_COMPANY, TEST_STATION, MockStations

from tests.common import MockConfigEntry


def _client_error(status: int) -> ClientResponseError:
    """Create an aiohttp client response error with a specific status code."""
    return ClientResponseError(
        request_info=Mock(),
        history=(),
        status=status,
        message="error",
        headers=None,
    )


async def test_user_form(hass: HomeAssistant) -> None:
    """Test the initial user form is shown."""
    result = await hass.config_entries.flow.async_init(
        "dk_fuelprices", context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a full successful config flow."""
    result = await hass.config_entries.flow.async_init(
        "dk_fuelprices", context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: TEST_API_KEY},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "company_selection"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"company": TEST_COMPANY},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station_selection"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"station": TEST_STATION["name"]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fuelprices.dk"
    assert result["data"] == {CONF_API_KEY: TEST_API_KEY}
    assert len(result["subentries"]) == 1
    subentry = result["subentries"][0]
    assert subentry["subentry_type"] == "station"
    assert subentry["title"] == f"{TEST_COMPANY} - {TEST_STATION['name']}"
    assert subentry["unique_id"] == f"{TEST_COMPANY}_{TEST_STATION['id']}"
    assert subentry["data"] == {
        "company": TEST_COMPANY,
        "station": TEST_STATION,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_invalid_api_key(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
) -> None:
    """Test flow aborts when API key is invalid."""
    mock_braendstofpriser.list_companies.side_effect = _client_error(401)

    result = await hass.config_entries.flow.async_init(
        "dk_fuelprices", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: TEST_API_KEY},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_api_key"


async def test_user_flow_rate_limit(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
) -> None:
    """Test flow aborts when API rate limit is exceeded."""
    mock_braendstofpriser.list_companies.side_effect = _client_error(429)

    result = await hass.config_entries.flow.async_init(
        "dk_fuelprices", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "rate_limit_exceeded"


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
) -> None:
    """Test flow aborts on generic connection error."""
    mock_braendstofpriser.list_companies.side_effect = _client_error(500)

    result = await hass.config_entries.flow.async_init(
        "dk_fuelprices", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_company_selection_aborts_without_companies(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
) -> None:
    """Test company selection aborts if API returns no companies."""
    mock_braendstofpriser.list_companies.return_value = []

    result = await hass.config_entries.flow.async_init(
        "dk_fuelprices", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "rate_limit_exceeded"


async def test_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braendstofpriser: AsyncMock,
) -> None:
    """Test reauthentication updates API key."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new-api-key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"


async def test_reauth_error_paths(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braendstofpriser: AsyncMock,
) -> None:
    """Test reauth form errors for all handled HTTP statuses."""
    mock_config_entry.add_to_hass(hass)

    for status, expected_error in (
        (401, "invalid_api_key"),
        (429, "rate_limit_exceeded"),
        (500, "cannot_connect"),
    ):
        mock_braendstofpriser.list_companies.side_effect = _client_error(status)
        result = await mock_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "bad-key"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": expected_error}

    mock_braendstofpriser.list_companies.side_effect = None


async def test_subentry_flow_create(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test creating a station subentry."""
    new_station = {"id": 4321, "name": "Aarhus N"}
    mock_braendstofpriser.list_stations.return_value = MockStations(
        [TEST_STATION, new_station]
    )

    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "company_selection"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"company": TEST_COMPANY},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station_selection"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"station": new_station["name"]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_COMPANY} - {new_station['name']}"
    assert result["unique_id"] == f"{TEST_COMPANY}_{new_station['id']}"


async def test_subentry_flow_duplicate_station(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test subentry flow aborts for an already configured station."""
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"company": TEST_COMPANY},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"station": TEST_STATION["name"]},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "station_already_configured"


async def test_subentry_flow_api_init_error_no_api_key(hass: HomeAssistant) -> None:
    """Test subentry flow aborts when config entry has no API key."""
    config_entry = MockConfigEntry(
        domain="dk_fuelprices",
        title="Fuelprices.dk",
        version=1,
        data={},
        subentries_data=[],
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_api_key"


async def test_subentry_flow_api_init_error_statuses(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test subentry flow aborts for all API init error statuses."""
    for status, reason in (
        (401, "invalid_api_key"),
        (429, "rate_limit_exceeded"),
        (500, "cannot_connect"),
    ):
        mock_braendstofpriser.list_companies.side_effect = _client_error(status)
        result = await hass.config_entries.subentries.async_init(
            (init_integration.entry_id, "station"),
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == reason

    mock_braendstofpriser.list_companies.side_effect = None


async def test_subentry_flow_company_selection_without_companies(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test subentry flow aborts when no companies are returned."""
    mock_braendstofpriser.list_companies.return_value = []

    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "rate_limit_exceeded"
