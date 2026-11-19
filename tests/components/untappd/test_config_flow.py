"""Test the Untappd config flow."""

from http import HTTPStatus
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

from aiountappd import UntappdAuthenticationError, UntappdConnectionError, User
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.untappd.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import ACCESS_TOKEN, CLIENT_ID, CLIENT_SECRET, USER_ID

REDIRECT_URI = "https://example.com/auth/external/callback"

pytestmark = pytest.mark.usefixtures("current_request_with_host", "setup_credentials")


async def _complete_oauth(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str = ACCESS_TOKEN,
) -> ConfigFlowResult:
    """Complete the OAuth callback and token exchange."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        OAUTH2_TOKEN,
        json={"meta": {"http_code": 200}, "response": {"access_token": access_token}},
    )
    return await hass.config_entries.flow.async_configure(result["flow_id"])


@pytest.mark.usefixtures("mock_untappd_client")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full OAuth flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    parsed = urlparse(result["url"])
    query = {key: value[0] for key, value in parse_qs(parsed.query).items()}
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == OAUTH2_AUTHORIZE
    assert query["client_id"] == CLIENT_ID
    assert query["response_type"] == "code"
    assert query["redirect_url"] == REDIRECT_URI

    result = await _complete_oauth(hass, result, hass_client_no_auth, aioclient_mock)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "hopsfan"
    assert result["result"].unique_id == str(USER_ID)
    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"]["token"]["access_token"] == ACCESS_TOKEN

    # The code is exchanged with a GET request carrying the client credentials.
    _, url, _, _ = aioclient_mock.mock_calls[0]
    assert url.query["client_secret"] == CLIENT_SECRET
    assert url.query["code"] == "abcd"
    assert url.query["redirect_url"] == REDIRECT_URI
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_untappd_client")
async def test_token_exchange_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a failing code exchange aborts the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.get(
        OAUTH2_TOKEN,
        status=500,
        json={
            "meta": {"code": 500, "error_type": "invalid_auth", "error_detail": "x"},
            "response": [],
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_failed"


@pytest.mark.usefixtures("mock_untappd_client")
async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding an account twice aborts."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await _complete_oauth(hass, result, hass_client_no_auth, aioclient_mock)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (UntappdAuthenticationError, "invalid_auth"),
        (UntappdConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_user_info_errors(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_untappd_client: AsyncMock,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test errors while fetching the account abort the flow."""
    mock_untappd_client.get_user_info.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await _complete_oauth(hass, result, hass_client_no_auth, aioclient_mock)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_untappd_client")
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauthentication updates the token."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await _complete_oauth(
        hass, result, hass_client_no_auth, aioclient_mock, "new-token"
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data["token"]["access_token"] == "new-token"


async def test_reauth_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    mock_untappd_client: AsyncMock,
) -> None:
    """Test reauthenticating with another account aborts."""
    mock_config_entry.add_to_hass(hass)
    user: User = mock_untappd_client.get_user_info.return_value
    mock_untappd_client.get_user_info.return_value = User.from_dict(
        user.to_dict() | {"uid": 1}
    )
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await _complete_oauth(
        hass, result, hass_client_no_auth, aioclient_mock, "new-token"
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data["token"]["access_token"] == ACCESS_TOKEN
