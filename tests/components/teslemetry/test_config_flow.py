"""Test the Teslemetry config flow."""

import time
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from aiohttp import ClientConnectionError
import pytest
from tesla_fleet_api.exceptions import (
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
)

from homeassistant.components.teslemetry.const import (
    AUTHORIZE_URL,
    CLIENT_ID,
    DOMAIN,
    TOKEN_URL,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import setup_platform
from .const import CONFIG_V1, UNIQUE_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT = "https://example.com/auth/external/callback"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    assert result["url"].startswith(AUTHORIZE_URL)
    parsed_url = urlparse(result["url"])
    parsed_query = parse_qs(parsed_url.query)
    assert parsed_query["response_type"][0] == "code"
    assert parsed_query["client_id"][0] == CLIENT_ID
    assert parsed_query["redirect_uri"][0] == REDIRECT
    assert parsed_query["state"][0] == state
    assert parsed_query["code_challenge"][0]

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    response = {
        "refresh_token": "test_refresh_token",
        "access_token": "test_access_token",
        "type": "Bearer",
        "expires_in": 60,
    }

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        TOKEN_URL,
        json=response,
    )

    # Complete OAuth
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UNIQUE_ID
    assert result["data"]["auth_implementation"] == "teslemetry"
    assert result["data"]["token"]["refresh_token"] == response["refresh_token"]
    assert result["data"]["token"]["access_token"] == response["access_token"]
    assert result["data"]["token"]["type"] == response["type"]
    assert result["data"]["token"]["expires_in"] == response["expires_in"]
    assert "expires_at" in result["result"].data["token"]


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauth flow."""

    mock_entry = await setup_platform(hass, [])

    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    # Progress from reauth_confirm to external OAuth step
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "test_refresh_token",
            "access_token": "test_access_token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test Tesla Fleet reauthentication with different account."""
    # Create an entry with a different unique_id to test account mismatch
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="baduid",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old_access_token",
                "refresh_token": "old_refresh_token",
                "expires_at": int(time.time()) + 3600,
            },
        },
    )
    old_entry.add_to_hass(hass)

    # Setup the integration properly to import client credentials
    await hass.config_entries.async_setup(old_entry.entry_id)
    await hass.async_block_till_done()

    result = await old_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "test_access_token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_account_mismatch"


@pytest.mark.usefixtures("current_request_with_host")
async def test_duplicate_unique_id_abort(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test duplicate unique ID aborts flow."""
    # Create existing entry
    await setup_platform(hass, [])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    # Complete OAuth - should abort due to duplicate unique_id
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    "exception",
    [
        InvalidToken,
        SubscriptionRequired,
        ClientConnectionError,
        TeslaFleetError("API error"),
    ],
)
async def test_oauth_error_handling(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    exception: Exception,
) -> None:
    """Test OAuth flow with various API errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "test_refresh_token",
            "access_token": "test_access_token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
) -> None:
    """Test reconfigure flow."""
    mock_entry = await setup_platform(hass, [])
    client = await hass_client_no_auth()

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    new_token_response = mock_token_response | {
        "refresh_token": "new_refresh_token",
        "access_token": "new_access_token",
    }
    aioclient_mock.post(TOKEN_URL, json=new_token_response)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Verify entry data was updated
    assert mock_entry.data["auth_implementation"] == DOMAIN
    assert mock_entry.data["token"]["refresh_token"] == "new_refresh_token"
    assert mock_entry.data["token"]["access_token"] == "new_access_token"
    assert mock_entry.data["token"]["type"] == "Bearer"
    assert mock_entry.data["token"]["expires_in"] == 60
    assert "expires_at" in mock_entry.data["token"]


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
) -> None:
    """Test reconfigure with different account."""
    # Create an entry with a different unique_id to test account mismatch
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="baduid",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old_access_token",
                "refresh_token": "old_refresh_token",
                "expires_at": int(time.time()) + 3600,
            },
        },
    )
    old_entry.add_to_hass(hass)

    # Setup the integration properly to import client credentials
    await hass.config_entries.async_setup(old_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    result = await old_entry.start_reconfigure_flow(hass)

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(TOKEN_URL, json=mock_token_response)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_account_mismatch"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    "exception",
    [
        InvalidToken,
        SubscriptionRequired,
        ClientConnectionError,
        TeslaFleetError("API error"),
    ],
)
async def test_reconfigure_oauth_error_handling(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
    exception: Exception,
) -> None:
    """Test reconfigure flow with various API errors."""
    mock_entry = await setup_platform(hass, [])
    client = await hass_client_no_auth()

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(TOKEN_URL, json=mock_token_response)

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_oauth_error_recovery(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
) -> None:
    """Test reconfigure flow can recover from an OAuth error."""
    mock_entry = await setup_platform(hass, [])
    client = await hass_client_no_auth()

    # First attempt - simulate OAuth error
    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(TOKEN_URL, json=mock_token_response)

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        side_effect=ClientConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"

    # Second attempt - should succeed (recovery)
    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.clear_requests()
    new_token_response = mock_token_response | {
        "refresh_token": "new_refresh_token",
        "access_token": "new_access_token",
    }
    aioclient_mock.post(TOKEN_URL, json=new_token_response)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Verify entry data was updated after recovery
    assert mock_entry.data["token"]["refresh_token"] == "new_refresh_token"
    assert mock_entry.data["token"]["access_token"] == "new_access_token"


async def test_migrate_error_from_future(
    hass: HomeAssistant, mock_metadata: AsyncMock
) -> None:
    """Test a future version isn't migrated."""

    mock_metadata.side_effect = TeslaFleetError

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        minor_version=1,
        unique_id="abc-123",
        data=CONFIG_V1,
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
