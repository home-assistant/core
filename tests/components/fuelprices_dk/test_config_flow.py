"""Test the Fuelprices.dk config flow."""

from collections.abc import Callable
from unittest.mock import AsyncMock, Mock

from aiohttp import ClientResponseError
from pybraendstofpriser import Flist
import pytest

from homeassistant.components.fuelprices_dk.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import TEST_API_KEY, TEST_COMPANY, TEST_STATION

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


def _client_error(status: int) -> ClientResponseError:
    """Create an aiohttp client response error with a specific status code."""
    return ClientResponseError(
        request_info=Mock(),
        history=(),
        status=status,
        message="error",
        headers=None,
    )


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a full successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "company_selection"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"company": TEST_COMPANY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station_selection"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"station": TEST_STATION["name"]}
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
    assert subentry["data"] == {"company": TEST_COMPANY, "station": TEST_STATION}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, "invalid_api_key"),
        (429, "rate_limit_exceeded"),
        (500, "cannot_connect"),
    ],
)
async def test_user_flow_recovers_from_api_errors(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    status: int,
    error: str,
) -> None:
    """Test the user flow shows an error and then recovers."""
    mock_braendstofpriser.list_companies.side_effect = _client_error(status)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_braendstofpriser.list_companies.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "company_selection"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"company": TEST_COMPANY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"station": TEST_STATION["name"]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_recovers_without_companies(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
) -> None:
    """Test the user flow recovers when the API returns no companies."""
    mock_braendstofpriser.list_companies.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_braendstofpriser.list_companies.return_value = [{"company": TEST_COMPANY}]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "company_selection"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"company": TEST_COMPANY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"station": TEST_STATION["name"]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate_api_key_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test flow aborts when the same API key is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "configure_stations",
    [
        lambda mock: setattr(mock.list_stations, "side_effect", _client_error(500)),
        lambda mock: setattr(mock.list_stations, "return_value", Flist([])),
    ],
    ids=["error", "empty"],
)
async def test_user_flow_station_error_returns_to_company_selection(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    configure_stations: Callable[[AsyncMock], None],
) -> None:
    """Test station loading errors return the user to company selection."""
    configure_stations(mock_braendstofpriser)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"company": TEST_COMPANY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "company_selection"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_braendstofpriser.list_stations.side_effect = None
    mock_braendstofpriser.list_stations.return_value = Flist([TEST_STATION])
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"company": TEST_COMPANY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"station": TEST_STATION["name"]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_allows_different_api_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braendstofpriser: AsyncMock,
) -> None:
    """Test flow allows a different API key."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "other-api-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "company_selection"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"company": TEST_COMPANY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"station": TEST_STATION["name"]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "other-api-key"}


async def test_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braendstofpriser: AsyncMock,
) -> None:
    """Test reauthentication updates the API key."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, "invalid_api_key"),
        (429, "rate_limit_exceeded"),
        (500, "cannot_connect"),
    ],
)
async def test_reauth_recovers_from_api_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braendstofpriser: AsyncMock,
    status: int,
    error: str,
) -> None:
    """Test reauth shows an error and then recovers."""
    mock_config_entry.add_to_hass(hass)
    mock_braendstofpriser.list_companies.side_effect = _client_error(status)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bad-key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_braendstofpriser.list_companies.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_subentry_flow_create(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a station subentry."""
    await setup_integration(hass, mock_config_entry)

    new_station = {"id": 4321, "name": "Aarhus N"}
    mock_braendstofpriser.list_stations.return_value = Flist(
        [TEST_STATION, new_station]
    )

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "company_selection"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"company": TEST_COMPANY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station_selection"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"station": new_station["name"]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_COMPANY} - {new_station['name']}"
    assert result["unique_id"] == f"{TEST_COMPANY}_{new_station['id']}"


async def test_subentry_flow_duplicate_station(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test subentry flow aborts for an already configured station."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"company": TEST_COMPANY}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"station": TEST_STATION["name"]}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "station_already_configured"


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (401, "invalid_api_key"),
        (429, "rate_limit_exceeded"),
        (500, "cannot_connect"),
    ],
)
async def test_subentry_flow_api_init_error(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    status: int,
    reason: str,
) -> None:
    """Test subentry flow aborts for API init errors."""
    await setup_integration(hass, mock_config_entry)
    mock_braendstofpriser.list_companies.side_effect = _client_error(status)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_subentry_flow_no_companies_aborts(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test subentry flow aborts when no companies are returned."""
    await setup_integration(hass, mock_config_entry)
    mock_braendstofpriser.list_companies.return_value = []

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    "configure_stations",
    [
        lambda mock: setattr(mock.list_stations, "side_effect", _client_error(500)),
        lambda mock: setattr(mock.list_stations, "return_value", Flist([])),
    ],
    ids=["error", "empty"],
)
async def test_subentry_flow_station_error_returns_to_company_selection(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    configure_stations: Callable[[AsyncMock], None],
) -> None:
    """Test station loading errors return the user to company selection."""
    await setup_integration(hass, mock_config_entry)

    configure_stations(mock_braendstofpriser)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"company": TEST_COMPANY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "company_selection"
    assert result["errors"] == {"base": "cannot_connect"}

    new_station = {"id": 4321, "name": "Aarhus N"}
    mock_braendstofpriser.list_stations.side_effect = None
    mock_braendstofpriser.list_stations.return_value = Flist(
        [TEST_STATION, new_station]
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"company": TEST_COMPANY}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"station": new_station["name"]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
