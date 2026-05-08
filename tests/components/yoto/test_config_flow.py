"""Tests for the Yoto config flow."""

from http import HTTPStatus
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import aiohttp
import pytest

from homeassistant.components.yoto.config_flow import FAMILY_ENDPOINT
from homeassistant.components.yoto.const import DOMAIN, YOTO_AUDIENCE, YOTO_SCOPES
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT_URI = "https://example.com/auth/external/callback"
TOKEN_URL = "https://login.yotoplay.com/oauth/token"
FAMILY_RESPONSE = {"family": {"familyId": "family-test"}}


async def _initiate_user_flow(hass: HomeAssistant) -> dict:
    """Start the OAuth2 user flow and return the EXTERNAL_STEP result."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def _complete_callback(
    hass: HomeAssistant,
    result: dict,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    *,
    refresh_token: str = "mock-refresh-token",
    access_token: str = "mock-access-token",
) -> dict:
    """Drive the OAuth2 callback through the token exchange."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI},
    )
    client = await hass_client_no_auth()
    response = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert response.status == HTTPStatus.OK

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": refresh_token,
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )
    return result


async def test_abort_if_no_credentials(hass: HomeAssistant) -> None:
    """The flow aborts when no application credentials are configured."""
    result = await _initiate_user_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Walk a happy-path OAuth2 flow end to end."""
    result = await _initiate_user_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    parsed = urlparse(result["url"])
    query = {key: value[0] for key, value in parse_qs(parsed.query).items()}
    assert parsed.scheme == "https"
    assert parsed.netloc == "login.yotoplay.com"
    assert parsed.path == "/authorize"
    assert query["audience"] == YOTO_AUDIENCE
    assert query["scope"] == " ".join(YOTO_SCOPES)
    assert query["client_id"] == "CLIENT_ID"
    assert query["redirect_uri"] == REDIRECT_URI

    await _complete_callback(hass, result, hass_client_no_auth, aioclient_mock)
    aioclient_mock.get(FAMILY_ENDPOINT, json=FAMILY_RESPONSE)

    with patch("homeassistant.components.yoto.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Yoto"
    assert result["result"].unique_id == "family-test"
    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"]["token"]["access_token"] == "mock-access-token"


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Re-authorizing the same family aborts as already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await _initiate_user_flow(hass)
    await _complete_callback(hass, result, hass_client_no_auth, aioclient_mock)
    aioclient_mock.get(FAMILY_ENDPOINT, json=FAMILY_RESPONSE)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_family_lookup_unauthorized(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The flow surfaces an OAuth error when the API rejects the token."""
    result = await _initiate_user_flow(hass)
    await _complete_callback(hass, result, hass_client_no_auth, aioclient_mock)
    aioclient_mock.get(FAMILY_ENDPOINT, status=401, json={"message": "denied"})

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_unauthorized"


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_family_lookup_connection_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A network failure on the family lookup surfaces as a connection error."""
    result = await _initiate_user_flow(hass)
    await _complete_callback(hass, result, hass_client_no_auth, aioclient_mock)
    aioclient_mock.get(FAMILY_ENDPOINT, exc=aiohttp.ClientError("boom"))

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "connection_error"


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_no_family_returned(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The flow aborts when no Yoto family is associated with the account."""
    result = await _initiate_user_flow(hass)
    await _complete_callback(hass, result, hass_client_no_auth, aioclient_mock)
    aioclient_mock.get(FAMILY_ENDPOINT, json={"family": None})

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_family"


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_reauth_success(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reauth refreshes the stored token data."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await _complete_callback(
        hass,
        result,
        hass_client_no_auth,
        aioclient_mock,
        refresh_token="rotated-refresh",
        access_token="rotated-access",
    )
    aioclient_mock.get(FAMILY_ENDPOINT, json=FAMILY_RESPONSE)

    with patch("homeassistant.components.yoto.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data["token"]["access_token"] == "rotated-access"


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_reauth_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reauth fails when the user authorizes a different family."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    await _complete_callback(hass, result, hass_client_no_auth, aioclient_mock)
    aioclient_mock.get(FAMILY_ENDPOINT, json={"family": {"familyId": "other-family"}})

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "account_mismatch"
