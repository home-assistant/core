"""Tests for Tibber config flow."""

from asyncio import TimeoutError
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from urllib.parse import parse_qs, urlparse

from aiohttp import ClientError
import pytest
from tibber import (
    FatalHttpExceptionError,
    InvalidLoginError,
    RetryableHttpExceptionError,
)

from homeassistant import config_entries
from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.application_credentials import TOKEN_URL
from homeassistant.components.tibber.config_flow import (
    APPLICATION_CREDENTIALS_DOC_URL,
    DATA_API_DOC_URL,
    ERR_CLIENT,
    ERR_TIMEOUT,
    ERR_TOKEN,
)
from homeassistant.components.tibber.const import (
    API_TYPE_DATA_API,
    API_TYPE_GRAPHQL,
    CONF_API_TYPE,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture(name="tibber_setup", autouse=True)
def tibber_setup_fixture():
    """Patch tibber setup entry."""
    with patch("homeassistant.components.tibber.async_setup_entry", return_value=True):
        yield


async def test_show_config_form(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test create entry from user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TYPE: API_TYPE_GRAPHQL}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "graphql"

    test_data = {CONF_ACCESS_TOKEN: "valid"}
    unique_user_id = "unique_user_id"
    title = "title"

    tibber_mock = MagicMock()
    type(tibber_mock).update_info = AsyncMock(return_value=True)
    type(tibber_mock).user_id = PropertyMock(return_value=unique_user_id)
    type(tibber_mock).name = PropertyMock(return_value=title)

    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], test_data
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == title
    assert result["data"] == {
        CONF_API_TYPE: API_TYPE_GRAPHQL,
        CONF_ACCESS_TOKEN: "valid",
    }


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (TimeoutError, ERR_TIMEOUT),
        (ClientError, ERR_CLIENT),
        (InvalidLoginError(401), ERR_TOKEN),
        (RetryableHttpExceptionError(503), ERR_CLIENT),
        (FatalHttpExceptionError(404), ERR_CLIENT),
    ],
)
async def test_create_entry_exceptions(
    recorder_mock: Recorder, hass: HomeAssistant, exception, expected_error
) -> None:
    """Test create entry from user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TYPE: API_TYPE_GRAPHQL}
    )

    unique_user_id = "unique_user_id"
    title = "title"

    tibber_mock = MagicMock()
    type(tibber_mock).update_info = AsyncMock(side_effect=exception)
    type(tibber_mock).user_id = PropertyMock(return_value=unique_user_id)
    type(tibber_mock).name = PropertyMock(return_value=title)

    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "valid"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"][CONF_ACCESS_TOKEN] == expected_error


async def test_flow_entry_already_exists(
    recorder_mock: Recorder, hass: HomeAssistant, config_entry
) -> None:
    """Test user input for config_entry that already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TYPE: API_TYPE_GRAPHQL}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_data_api_requires_credentials(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test the data API path aborts when no credentials are configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TYPE: API_TYPE_DATA_API}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"
    assert result["description_placeholders"] == {
        "application_credentials_url": APPLICATION_CREDENTIALS_DOC_URL,
        "data_api_url": DATA_API_DOC_URL,
    }


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_data_api_full_flow(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test configuring the Data API through OAuth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TYPE: API_TYPE_DATA_API}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    authorize_url = result["url"]
    state = parse_qs(urlparse(authorize_url).query)["state"][0]

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )

    data_api_client = MagicMock()
    data_api_client.get_userinfo = AsyncMock(
        return_value={"email": "mock-user@example.com"}
    )

    with patch(
        "homeassistant.components.tibber.config_flow.TibberDataAPI",
        return_value=data_api_client,
        create=True,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_TYPE] == API_TYPE_DATA_API
    assert result["data"][CONF_TOKEN]["access_token"] == "mock-access-token"
    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["title"] == "mock-user@example.com"
    assert result["result"].unique_id == "mock-user@example.com"
