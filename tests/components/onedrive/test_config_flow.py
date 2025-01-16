"""Test the OneDrive config flow."""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

from kiota_abstractions.api_error import APIError
from msgraph.generated.models.drive import Drive
import pytest

from homeassistant import config_entries, setup
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.onedrive.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    OAUTH_SCOPES,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import setup_integration
from .const import CLIENT_ID, CLIENT_SECRET

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def _do_get_token(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    scope = "+".join(OAUTH_SCOPES)

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={scope}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )


async def _setup_oauth_step(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> ConfigFlowResult:
    """Set up the OAuth2 flow."""
    assert await setup.async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), "imported-cred"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)

    return result


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """Check full flow."""

    result = await _setup_oauth_step(hass, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["title"] == "John Doe's OneDrive"


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_drive_in_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_drive: Drive,
) -> None:
    """Test no drive in account."""

    mock_drive.id = None

    result = await _setup_oauth_step(hass, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_drive"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    (
        "exception",
        "error",
    ),
    [
        (Exception, "unknown"),
        (APIError, "connection_error"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_graph_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test errors during flow."""

    mock_graph_client.me.drive.get = AsyncMock(side_effect=exception)

    result = await _setup_oauth_step(hass, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error


@pytest.mark.usefixtures("current_request_with_host")
async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test already configured account."""
    await setup_integration(hass, mock_config_entry)

    result = await _setup_oauth_step(hass, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the reauth flow works."""

    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_flow_id_changed(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_drive: Drive,
) -> None:
    """Test that the reauth flow fails on a different drive id."""
    mock_drive.id = "other-drive-id"
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_drive"
