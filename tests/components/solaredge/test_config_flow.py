"""Tests for the SolarEdge config flow."""

from unittest.mock import AsyncMock, Mock

from aiohttp import ClientError, ClientResponseError
import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.solaredge.const import CONF_SITE_ID, DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_KEY, PASSWORD, SITE_ID, USERNAME

from tests.common import MockConfigEntry

NAME = "solaredge site 1 2 3"


@pytest.fixture(autouse=True)
def solaredge_api_fixture(solaredge_api: Mock) -> None:
    """Mock the solaredge API."""


@pytest.fixture(autouse=True)
def solaredge_web_api_fixture(solaredge_web_api: AsyncMock) -> None:
    """Mock the solaredge web API."""


async def test_user_api_key(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    solaredge_api: Mock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user config with API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "solaredge_site_1_2_3"

    data = result.get("data")
    assert data
    assert data[CONF_SITE_ID] == SITE_ID
    assert data[CONF_API_KEY] == API_KEY
    assert CONF_USERNAME not in data
    assert CONF_PASSWORD not in data

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_web_login(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    solaredge_web_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user config with web login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: NAME,
            CONF_SITE_ID: SITE_ID,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "solaredge_site_1_2_3"

    data = result.get("data")
    assert data
    assert data[CONF_SITE_ID] == SITE_ID
    assert data[CONF_USERNAME] == USERNAME
    assert data[CONF_PASSWORD] == PASSWORD
    assert CONF_API_KEY not in data

    assert len(mock_setup_entry.mock_calls) == 1
    solaredge_web_api.async_get_equipment.assert_awaited_once()


async def test_user_both_auth(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    solaredge_api: Mock,
    solaredge_web_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user config with both API key and web login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: NAME,
            CONF_SITE_ID: SITE_ID,
            CONF_API_KEY: API_KEY,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    data = result.get("data")
    assert data
    assert data[CONF_SITE_ID] == SITE_ID
    assert data[CONF_API_KEY] == API_KEY
    assert data[CONF_USERNAME] == USERNAME
    assert data[CONF_PASSWORD] == PASSWORD

    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_if_already_setup(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test we abort if the site_id is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: DEFAULT_NAME, CONF_SITE_ID: SITE_ID, CONF_API_KEY: API_KEY},
    ).add_to_hass(hass)

    # Should fail, same SITE_ID
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NAME: "test", CONF_SITE_ID: SITE_ID, CONF_API_KEY: "test"},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {CONF_SITE_ID: "already_configured"}


async def test_ignored_entry_does_not_cause_error(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test an ignored entry does not cause and error and we can still create an new entry."""
    MockConfigEntry(
        domain="solaredge",
        data={CONF_NAME: DEFAULT_NAME, CONF_API_KEY: API_KEY},
        source=SOURCE_IGNORE,
    ).add_to_hass(hass)

    # Should not fail, same SITE_ID
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NAME: "test", CONF_SITE_ID: SITE_ID, CONF_API_KEY: "test"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"

    data = result["data"]
    assert data
    assert data[CONF_SITE_ID] == SITE_ID
    assert data[CONF_API_KEY] == "test"


async def test_no_auth_provided(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test error when no authentication method is provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: NAME, CONF_SITE_ID: SITE_ID},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "auth_missing"}


@pytest.mark.parametrize(
    ("api_setup", "expected_error"),
    [
        ({"return_value": {"details": {"status": "NOK"}}}, "site_not_active"),
        ({"return_value": {}}, "invalid_api_key"),
        ({"side_effect": TimeoutError()}, "cannot_connect"),
        ({"side_effect": ClientError()}, "cannot_connect"),
    ],
)
async def test_api_key_errors(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    solaredge_api: Mock,
    api_setup: dict,
    expected_error: str,
) -> None:
    """Test API key validation errors."""
    if "side_effect" in api_setup:
        solaredge_api.get_details.side_effect = api_setup["side_effect"]
    else:
        solaredge_api.get_details.return_value = api_setup["return_value"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {CONF_SITE_ID: expected_error}


@pytest.mark.parametrize(
    ("api_exception", "expected_error"),
    [
        (ClientResponseError(None, None, status=401), "invalid_auth"),
        (ClientResponseError(None, None, status=403), "invalid_auth"),
        (ClientResponseError(None, None, status=400), "cannot_connect"),
        (ClientResponseError(None, None, status=500), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (ClientError(), "cannot_connect"),
    ],
)
async def test_web_login_errors(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    solaredge_web_api: AsyncMock,
    api_exception: Exception,
    expected_error: str,
) -> None:
    """Test web login validation errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    solaredge_web_api.async_get_equipment.side_effect = api_exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: NAME,
            CONF_SITE_ID: SITE_ID,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": expected_error}
