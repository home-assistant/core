"""Test the Willow config flow."""

from http import HTTPStatus
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest

from homeassistant.components.willow.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_CLIENT_ID,
    OAUTH2_TOKEN,
)
from homeassistant.components.willow.exceptions import WillowAuthError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import ACCESS_TOKEN, IMPL_DOMAIN, REFRESH_TOKEN, USER_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT_URI = "https://example.com/auth/external/callback"

pytestmark = pytest.mark.usefixtures("current_request_with_host", "setup_credentials")


async def _initiate_user_flow(hass: HomeAssistant) -> dict:
    """Start the OAuth2 user flow and return the EXTERNAL_STEP result."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def _complete_oauth(
    hass: HomeAssistant,
    result: dict,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    *,
    access_token: str = ACCESS_TOKEN,
    refresh_token: str = REFRESH_TOKEN,
) -> None:
    """Drive the OAuth2 callback through the token exchange."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI},
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": refresh_token,
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_willow_client: MagicMock,
    mock_setup_entry,
) -> None:
    """Walk a happy-path OAuth2 flow end to end."""
    result = await _initiate_user_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI},
    )
    parsed = urlparse(result["url"])
    query = {key: value[0] for key, value in parse_qs(parsed.query).items()}
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == OAUTH2_AUTHORIZE
    assert query["response_type"] == "code"
    assert query["client_id"] == OAUTH2_CLIENT_ID
    assert query["redirect_uri"] == REDIRECT_URI
    assert query["state"] == state
    assert query["scope"] == "read"

    await _complete_oauth(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "garden@example.com"
    assert result["result"].unique_id == str(USER_ID)
    assert result["data"]["auth_implementation"] == IMPL_DOMAIN
    assert result["data"]["token"]["access_token"] == ACCESS_TOKEN
    mock_willow_client.get_profile.assert_awaited_once()


async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Authenticating an already-configured account aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await _initiate_user_flow(hass)
    await _complete_oauth(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (WillowAuthError, "invalid_auth"),
        (Exception("boom"), "unknown"),
    ],
)
async def test_profile_errors_abort(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_willow_client: MagicMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """A failing profile lookup aborts the flow with the mapped reason."""
    mock_willow_client.get_profile.side_effect = side_effect

    result = await _initiate_user_flow(hass)
    await _complete_oauth(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_reauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry,
) -> None:
    """Reauthorizing the same account updates the existing entry's token."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await _complete_oauth(
        hass,
        result,
        hass_client_no_auth,
        aioclient_mock,
        refresh_token="new-refresh-token",
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data["token"]["refresh_token"] == "new-refresh-token"


async def test_reauth_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry,
) -> None:
    """Reauthorizing with a different account aborts."""
    mock_config_entry.add_to_hass(hass)
    mock_willow_client.get_profile.return_value = {
        "id": 99,
        "username": "other@example.com",
        "profile_image": None,
    }

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await _complete_oauth(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
