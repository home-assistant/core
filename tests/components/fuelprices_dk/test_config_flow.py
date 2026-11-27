"""Test the Fuelprices.dk config flow."""

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientConnectionError
from pybraendstofpriser import Flist
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.fuelprices_dk.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE

from . import client_error, setup_integration
from .conftest import TEST_API_KEY, TEST_COMPANY, TEST_STATION

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


CONNECTION_FAILURES = (
    pytest.param(client_error(500), id="server_error"),
    pytest.param(ClientConnectionError(), id="connection_error"),
    pytest.param(TimeoutError(), id="timeout"),
)
COMPANY_FAILURES = (
    pytest.param(client_error(401), "invalid_api_key", id="invalid_api_key"),
    pytest.param(client_error(429), "rate_limit_exceeded", id="rate_limit"),
    pytest.param(client_error(500), "cannot_connect", id="server_error"),
    pytest.param(ClientConnectionError(), "cannot_connect", id="connection_error"),
    pytest.param(TimeoutError(), "cannot_connect", id="timeout"),
    pytest.param([], "cannot_connect", id="empty"),
)


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_braendstofpriser_class: MagicMock,
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
    mock_braendstofpriser_class.assert_called_once_with(
        TEST_API_KEY, user_agent=SERVER_SOFTWARE
    )


@pytest.mark.parametrize(("response", "error"), COMPANY_FAILURES)
async def test_user_flow_recovers_from_api_errors(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    response: Exception | list[dict[str, str]],
    error: str,
) -> None:
    """Test the user flow shows an error and then recovers."""
    mock_braendstofpriser.list_companies.side_effect = [
        response,
        [{"company": TEST_COMPANY}],
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

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
    "response",
    [*CONNECTION_FAILURES, pytest.param(Flist(), id="empty")],
)
async def test_user_flow_station_error_returns_to_company_selection(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    response: Exception | Flist[dict[str, int | str]],
) -> None:
    """Test station loading errors return the user to company selection."""
    mock_braendstofpriser.list_stations.side_effect = [response]

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
    """Test flow allows a different API key for a different station."""
    mock_config_entry.add_to_hass(hass)
    new_station = {"id": 4321, "name": "Aarhus N"}
    mock_braendstofpriser.list_stations.return_value = Flist(
        [TEST_STATION, new_station]
    )

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
        result["flow_id"], {"station": new_station["name"]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "other-api-key"}


@pytest.mark.parametrize(
    ("api_key", "station_name", "reason"),
    [
        pytest.param(TEST_API_KEY, "Aarhus N", "already_configured", id="same_key"),
        pytest.param(
            "other-api-key",
            TEST_STATION["name"],
            "station_already_configured",
            id="same_station",
        ),
    ],
)
async def test_overlapping_setup_flows_reject_duplicates(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    api_key: str,
    station_name: str,
    reason: str,
) -> None:
    """Test setup rechecks for duplicates after another flow finishes."""
    mock_braendstofpriser.list_stations.return_value = Flist(
        [TEST_STATION, {"id": 4321, "name": "Aarhus N"}]
    )
    first_flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second_flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        first_flow["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )
    await hass.config_entries.flow.async_configure(
        second_flow["flow_id"], {CONF_API_KEY: api_key}
    )
    first = await hass.config_entries.flow.async_configure(
        first_flow["flow_id"], {"company": TEST_COMPANY}
    )
    second = await hass.config_entries.flow.async_configure(
        second_flow["flow_id"], {"company": TEST_COMPANY}
    )
    assert first["step_id"] == second["step_id"] == "station_selection"

    first = await hass.config_entries.flow.async_configure(
        first_flow["flow_id"], {"station": TEST_STATION["name"]}
    )
    assert first["type"] is FlowResultType.CREATE_ENTRY
    second = await hass.config_entries.flow.async_configure(
        second_flow["flow_id"], {"station": station_name}
    )
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == reason
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braendstofpriser: AsyncMock,
    mock_braendstofpriser_class: MagicMock,
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
    mock_braendstofpriser_class.assert_called_once_with(
        "new-api-key", user_agent=SERVER_SOFTWARE
    )


async def test_reauth_rejects_api_key_used_by_another_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braendstofpriser: AsyncMock,
) -> None:
    """Test reauth cannot take another entry's API key."""
    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "other-api-key"})
    other.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: other.data[CONF_API_KEY]}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_API_KEY] == TEST_API_KEY


@pytest.mark.parametrize(("response", "error"), COMPANY_FAILURES)
async def test_reauth_recovers_from_api_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braendstofpriser: AsyncMock,
    response: Exception | list[dict[str, str]],
    error: str,
) -> None:
    """Test reauth shows an error and then recovers."""
    mock_config_entry.add_to_hass(hass)
    mock_braendstofpriser.list_companies.side_effect = [
        response,
        [{"company": TEST_COMPANY}],
    ]

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bad-key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_subentry_flow_create(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_braendstofpriser_class: MagicMock,
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
    mock_braendstofpriser_class.assert_called_once_with(
        TEST_API_KEY, user_agent=SERVER_SOFTWARE
    )


@pytest.mark.parametrize(
    "entry_index", [pytest.param(0, id="same_entry"), pytest.param(1, id="other_entry")]
)
async def test_subentry_flow_duplicate_station(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entry_index: int,
) -> None:
    """Test subentry flow aborts for an already configured station."""
    await setup_integration(hass, mock_config_entry)
    other = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "other-api-key"})
    other.add_to_hass(hass)
    entry = (mock_config_entry, other)[entry_index]

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "station"),
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
    mock_braendstofpriser.list_companies.side_effect = client_error(status)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize(
    "response",
    [*CONNECTION_FAILURES, pytest.param([], id="empty")],
)
async def test_subentry_flow_recovers_from_connection_error(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    response: Exception | list[dict[str, str]],
) -> None:
    """Test the user can retry loading companies in the same subentry flow."""
    await setup_integration(hass, mock_config_entry)
    mock_braendstofpriser.list_companies.side_effect = [
        response,
        [{"company": TEST_COMPANY}],
    ]
    new_station = {"id": 4321, "name": "Aarhus N"}
    mock_braendstofpriser.list_stations.return_value = Flist([new_station])

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "station"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "company_selection"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"company": TEST_COMPANY}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"station": new_station["name"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "response",
    [*CONNECTION_FAILURES, pytest.param(Flist(), id="empty")],
)
async def test_subentry_flow_station_error_returns_to_company_selection(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    response: Exception | Flist[dict[str, int | str]],
) -> None:
    """Test station loading errors return the user to company selection."""
    await setup_integration(hass, mock_config_entry)

    mock_braendstofpriser.list_stations.side_effect = [response]

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
