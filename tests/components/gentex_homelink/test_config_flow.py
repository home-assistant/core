"""Test the homelink config flow."""

from http import HTTPStatus

from homelink.settings import COGNITO_CLIENT_ID
import pytest

from homeassistant.components.gentex_homelink.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE_URL,
    OAUTH2_TOKEN_URL,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import (
    INVALID_TEST_ACCESS_JWT,
    TEST_ACCESS_JWT,
    TEST_UNIQUE_ID,
    setup_integration,
)

from tests.common import MockConfigEntry
from tests.conftest import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def complete_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    flow_id: str,
    access_token: str,
) -> ConfigFlowResult:
    """Complete the OAuth2 callback flow."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        json={
            "access_token": access_token,
            "refresh_token": "refresh",
            "expires_in": 3600,
            "token_type": "bearer",
        },
    )
    return await hass.config_entries.flow.async_configure(flow_id)


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE_URL}?response_type=code&client_id={COGNITO_CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], TEST_ACCESS_JWT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "auth_implementation": "gentex_homelink",
        "token": {
            "access_token": TEST_ACCESS_JWT,
            "refresh_token": "refresh",
            "expires_in": 3600,
            "token_type": "bearer",
            "expires_at": result["data"]["token"]["expires_at"],
        },
    }
    assert result["result"].unique_id == TEST_UNIQUE_ID
    assert result["title"] == "HomeLink"


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_unique_configurations(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Check full flow."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], TEST_ACCESS_JWT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_auth_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test if the auth server returns an error resolving the token."""
    aioclient_mock.clear_requests()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(OAUTH2_TOKEN_URL, status=HTTPStatus.UNAUTHORIZED)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][0] == "POST"
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_unauthorized"


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_successful(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], TEST_ACCESS_JWT
    )
    assert result["reason"] == "reauth_successful"
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await complete_oauth_flow(
        hass,
        hass_client_no_auth,
        aioclient_mock,
        result["flow_id"],
        INVALID_TEST_ACCESS_JWT,
    )
    assert result["reason"] == "unique_id_mismatch"
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.usefixtures("current_request_with_host")
async def test_invalid_token(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the flow aborts when the access token is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await complete_oauth_flow(
        hass,
        hass_client_no_auth,
        aioclient_mock,
        result["flow_id"],
        "not-a-valid-jwt-token",
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"
