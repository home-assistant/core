"""Tests for the Yoto config flow."""

from http import HTTPStatus
from urllib.parse import parse_qs, urlparse

import jwt
import pytest

from homeassistant.components.yoto.const import DOMAIN, YOTO_AUDIENCE, YOTO_SCOPES
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import ACCESS_TOKEN, USER_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT_URI = "https://example.com/auth/external/callback"
TOKEN_URL = "https://login.yotoplay.com/oauth/token"


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
    access_token: str = ACCESS_TOKEN,
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


@pytest.mark.usefixtures(
    "current_request_with_host", "setup_credentials", "mock_setup_entry"
)
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
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Yoto"
    assert result["result"].unique_id == USER_ID
    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"]["token"]["access_token"] == ACCESS_TOKEN


@pytest.mark.usefixtures(
    "current_request_with_host", "setup_credentials", "mock_setup_entry"
)
async def test_dhcp_discovery_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A Yoto player found on the LAN walks through OAuth to a new entry."""
    discovery = DhcpServiceInfo(
        ip="10.0.0.42",
        hostname="yoto-player",
        macaddress="6825dd39c3fc",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=discovery
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "oauth_discovery"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await _complete_callback(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USER_ID


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Re-authorizing the same account aborts as already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await _initiate_user_flow(hass)
    await _complete_callback(hass, result, hass_client_no_auth, aioclient_mock)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "access_token",
    [
        "not-a-jwt",
        jwt.encode({"foo": "bar"}, "test-secret-long-enough-for-hmac-sha256"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_invalid_access_token(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
) -> None:
    """The flow aborts when the access token is not a usable JWT."""
    result = await _initiate_user_flow(hass)
    await _complete_callback(
        hass, result, hass_client_no_auth, aioclient_mock, access_token=access_token
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_unauthorized"
