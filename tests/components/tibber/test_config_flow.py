"""Tests for Tibber config flow."""

import builtins
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch
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
    DATA_API_DEFAULT_SCOPES,
    ERR_CLIENT,
    ERR_TOKEN,
)
from homeassistant.components.tibber.const import AUTH_IMPLEMENTATION, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture(name="tibber_setup", autouse=True)
def tibber_setup_fixture():
    """Patch tibber setup entry."""
    with patch("homeassistant.components.tibber.async_setup_entry", return_value=True):
        yield


def _mock_tibber(
    tibber_mock: MagicMock,
    *,
    user_id: str = "unique_user_id",
    title: str = "Mock Name",
    update_side_effect: Exception | None = None,
) -> MagicMock:
    """Configure the patched Tibber GraphQL client."""
    tibber_mock.user_id = user_id
    tibber_mock.name = title
    tibber_mock.update_info = AsyncMock()
    if update_side_effect is not None:
        tibber_mock.update_info.side_effect = update_side_effect
    return tibber_mock


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (InvalidLoginError(401), ERR_TOKEN),
        (FatalHttpExceptionError(404), ERR_CLIENT),
    ],
)
async def test_oauth_create_entry_abort_exceptions(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    tibber_mock: MagicMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Validate fatal errors during OAuth finalization abort the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    handler = hass.config_entries.flow._progress[result["flow_id"]]

    _mock_tibber(tibber_mock, update_side_effect=exception)
    flow_result = await handler.async_oauth_create_entry(
        {CONF_TOKEN: {CONF_ACCESS_TOKEN: "rest-token"}}
    )

    assert flow_result["type"] is FlowResultType.ABORT
    assert flow_result["reason"] == expected_error


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
@pytest.mark.parametrize(
    "exception",
    [
        builtins.TimeoutError(),
        ClientError(),
        RetryableHttpExceptionError(503),
    ],
)
async def test_oauth_create_entry_connection_error_retry(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    tibber_mock: MagicMock,
    exception: Exception,
) -> None:
    """Validate transient connection errors show retry form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    _mock_tibber(tibber_mock, update_side_effect=exception)
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

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection_error"

    tibber_mock.update_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mock Name"


async def test_data_api_requires_credentials(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Abort when OAuth credentials are missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_data_api_extra_authorize_scope(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Ensure the OAuth implementation requests Tibber scopes."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    handler = hass.config_entries.flow._progress[result["flow_id"]]
    assert handler.extra_authorize_data["scope"] == " ".join(DATA_API_DEFAULT_SCOPES)


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_full_flow_success(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    tibber_mock: MagicMock,
) -> None:
    """Test configuring Tibber via OAuth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    _mock_tibber(tibber_mock)
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

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = result["data"]
    assert data[CONF_TOKEN]["access_token"] == "mock-access-token"
    assert data[AUTH_IMPLEMENTATION] == DOMAIN
    assert result["title"] == "Mock Name"


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_data_api_abort_when_already_configured(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    tibber_mock: MagicMock,
) -> None:
    """Ensure only a single Data API entry can be configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            AUTH_IMPLEMENTATION: DOMAIN,
            CONF_TOKEN: {"access_token": "existing"},
        },
        unique_id="unique_user_id",
        title="Existing",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    _mock_tibber(tibber_mock)
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

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_reauth_flow_success(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    tibber_mock: MagicMock,
) -> None:
    """Test successful reauthentication flow."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            AUTH_IMPLEMENTATION: DOMAIN,
            CONF_TOKEN: {"access_token": "old-token"},
        },
        unique_id="unique_user_id",
        title="Existing",
    )
    existing_entry.add_to_hass(hass)

    result = await existing_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    _mock_tibber(tibber_mock)
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    authorize_url = result["url"]
    state = parse_qs(urlparse(authorize_url).query)["state"][0]

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert existing_entry.data[CONF_TOKEN]["access_token"] == "new-access-token"


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_reauth_flow_wrong_account(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    tibber_mock: MagicMock,
) -> None:
    """Test reauthentication with wrong account aborts."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            AUTH_IMPLEMENTATION: DOMAIN,
            CONF_TOKEN: {"access_token": "old-token"},
        },
        unique_id="original_user_id",
        title="Existing",
    )
    existing_entry.add_to_hass(hass)

    result = await existing_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    # Mock a different user_id than the existing entry
    _mock_tibber(tibber_mock, user_id="different_user_id")
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    authorize_url = result["url"]
    state = parse_qs(urlparse(authorize_url).query)["state"][0]

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
