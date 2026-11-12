"""Test the GKP config flow."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant import config_entries
from homeassistant.components.gkp.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import TEST_USER_ID

TOKEN_RESPONSE = {
    "refresh_token": "mock-refresh-token",
    "access_token": "mock-access-token",
    "token_type": "Bearer",
    "expires_in": 3600,
}


async def _complete_oauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    flow_id: str,
    user_id: str | None,
) -> ConfigFlowResult:
    """Go through the OAuth2 callback and finish the flow as the given user."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(OAUTH2_TOKEN, json=TOKEN_RESPONSE)

    with patch(
        "homeassistant.components.gkp.config_flow.GkpAuth.extract_user_id_from_token",
        return_value=user_id,
    ):
        return await hass.config_entries.flow.async_configure(flow_id)


async def _start_reauth_flow(
    hass: HomeAssistant, entry: MockConfigEntry
) -> ConfigFlowResult:
    """Start a reauthentication flow up to the OAuth2 step."""
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    return await hass.config_entries.flow.async_configure(result["flow_id"], {})


async def _start_reconfigure_flow(
    hass: HomeAssistant, entry: MockConfigEntry
) -> ConfigFlowResult:
    """Start a reconfiguration flow up to the OAuth2 step."""
    return await entry.start_reconfigure_flow(hass)


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the full OAuth2 config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert OAUTH2_AUTHORIZE in result["url"]
    assert (
        "scope=openid+offline_access+Installation.Read"
        "+IOTManagement.Read+IOTManagement.Write"
    ) in result["url"]

    result = await _complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], TEST_USER_ID
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "GKP Home"
    assert result["result"].unique_id == TEST_USER_ID
    assert "token" in result["data"]


@pytest.mark.usefixtures("current_request_with_host")
async def test_invalid_token_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the flow aborts when no user can be read from the token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await _complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], None
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_token"


@pytest.mark.usefixtures("current_request_with_host")
async def test_unique_config_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the same account cannot be configured twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await _complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], TEST_USER_ID
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@pytest.mark.parametrize(
    ("start_flow", "reason"),
    [
        pytest.param(_start_reauth_flow, "reauth_successful", id="reauth"),
        pytest.param(
            _start_reconfigure_flow, "reconfigure_successful", id="reconfigure"
        ),
    ],
)
async def test_update_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    start_flow: Callable[[HomeAssistant, MockConfigEntry], Awaitable[ConfigFlowResult]],
    reason: str,
) -> None:
    """Test reauthentication and reconfiguration update the token."""
    mock_config_entry.add_to_hass(hass)
    result = await start_flow(hass, mock_config_entry)

    result = await _complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], TEST_USER_ID
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    mock_config_entry.data["token"].pop("expires_at")
    assert mock_config_entry.data["token"] == TOKEN_RESPONSE


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    "start_flow",
    [
        pytest.param(_start_reauth_flow, id="reauth"),
        pytest.param(_start_reconfigure_flow, id="reconfigure"),
    ],
)
async def test_update_flow_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    start_flow: Callable[[HomeAssistant, MockConfigEntry], Awaitable[ConfigFlowResult]],
) -> None:
    """Test reauthentication and reconfiguration with another account abort."""
    mock_config_entry.add_to_hass(hass)
    result = await start_flow(hass, mock_config_entry)

    result = await _complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], "other-user-id"
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "account_mismatch"
