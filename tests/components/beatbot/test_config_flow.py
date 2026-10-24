"""Tests for the Beatbot OAuth2 config flow."""

import base64
import json
from typing import Any
from unittest.mock import MagicMock

from beatbot_cloud import BeatbotAuthenticationError, BeatbotConnectionError
from beatbot_cloud.const import OAUTH2_AUTHORIZE_URL, OAUTH2_CLIENT_ID, OAUTH2_SCOPE
import pytest

from homeassistant.components.beatbot.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import TOKEN_URL

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT_URI = "https://example.com/auth/external/callback"

pytestmark = pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")


def _make_access_token(sub: object, *, region: str | None = "cn") -> str:
    """Build a JWT whose claims the library reads without verifying the signature."""
    claims: dict[str, Any] = {"sub": sub}
    if region is not None:
        claims["region"] = region
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
    return f"header.{payload.decode()}.signature"


def _token_response(sub: object = "account-1", *, region: str | None = "cn") -> dict:
    """Return an OAuth token response carrying the given account claims."""
    return {
        "access_token": _make_access_token(sub, region=region),
        "refresh_token": "mock-refresh-token",
        "token_type": "bearer",
        "expires_in": 3600,
        "scope": OAUTH2_SCOPE,
    }


async def _start_flow(hass: HomeAssistant) -> dict:
    """Start a user flow and return its external authorization step."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def _complete_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    flow_id: str,
) -> dict:
    """Finish the external OAuth step and return the flow result."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {"flow_id": flow_id, "redirect_uri": REDIRECT_URI},
    )
    client = await hass_client_no_auth()
    response = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert response.status == 200
    return await hass.config_entries.flow.async_configure(flow_id)


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_client_class: MagicMock,
) -> None:
    """Authorize an account, validate its region and create one entry."""
    result = await _start_flow(hass)
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI},
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    url = result["url"]
    assert url.startswith(f"{OAUTH2_AUTHORIZE_URL}?")
    assert f"client_id={OAUTH2_CLIENT_ID}" in url
    assert f"redirect_uri={REDIRECT_URI}" in url
    assert f"state={state}" in url
    assert f"scope={OAUTH2_SCOPE}" in url
    assert "code_challenge=" in url

    aioclient_mock.post(TOKEN_URL, json=_token_response())
    result = await _complete_flow(hass, hass_client_no_auth, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Beatbot"
    assert result["result"].unique_id == "account-1"
    assert result["result"].data["region"] == "cn"
    assert result["result"].data["auth_implementation"] == DOMAIN
    assert result["result"].data["token"]["access_token"] == _make_access_token(
        "account-1"
    )
    assert mock_client_class.call_args.args[0] == "cn"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        pytest.param(BeatbotAuthenticationError(), "oauth_error", id="authentication"),
        pytest.param(
            BeatbotConnectionError("offline"), "cannot_connect", id="connection"
        ),
    ],
)
async def test_flow_aborts_on_resource_api_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_client: MagicMock,
    error: Exception,
    reason: str,
) -> None:
    """Abort when the regional device API rejects the new token."""
    aioclient_mock.post(TOKEN_URL, json=_token_response())
    mock_client.get_devices.side_effect = error

    result = await _start_flow(hass)
    result = await _complete_flow(hass, hass_client_no_auth, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize("sub", ["", 123, None])
async def test_flow_aborts_without_account_subject(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_client: MagicMock,
    sub: object,
) -> None:
    """Reject tokens without a non-empty string account subject."""
    aioclient_mock.post(TOKEN_URL, json=_token_response(sub))

    result = await _start_flow(hass)
    result = await _complete_flow(hass, hass_client_no_auth, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize("region", ["zz", None])
async def test_flow_aborts_with_unknown_region(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_client: MagicMock,
    region: str | None,
) -> None:
    """Abort without a region the API base URLs cover."""
    aioclient_mock.post(TOKEN_URL, json=_token_response(region=region))

    result = await _start_flow(hass)
    result = await _complete_flow(hass, hass_client_no_auth, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown_region"
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        pytest.param(500, "oauth_failed", id="server-error"),
        pytest.param(401, "oauth_unauthorized", id="rejected-token"),
    ],
)
async def test_flow_aborts_on_token_endpoint_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_client: MagicMock,
    status: int,
    reason: str,
) -> None:
    """Abort with the reason matching the token endpoint failure."""
    aioclient_mock.post(TOKEN_URL, status=status)

    result = await _start_flow(hass)
    result = await _complete_flow(hass, hass_client_no_auth, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_flow_aborts_on_token_without_expiry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_client: MagicMock,
) -> None:
    """Reject a token response that does not say when the token expires."""
    token = _token_response()
    del token["expires_in"]
    aioclient_mock.post(TOKEN_URL, json=token)

    result = await _start_flow(hass)
    result = await _complete_flow(hass, hass_client_no_auth, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_flow_aborts_when_authorization_is_rejected(
    hass: HomeAssistant,
) -> None:
    """Surface a rejected authorization as user_rejected_authorize."""
    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"error": "access_denied", "state": {"flow_id": result["flow_id"]}},
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "user_rejected_authorize"


async def test_flow_aborts_for_configured_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Refuse to configure the same Beatbot account twice."""
    mock_config_entry.add_to_hass(hass)
    aioclient_mock.post(TOKEN_URL, json=_token_response())

    result = await _start_flow(hass)
    result = await _complete_flow(hass, hass_client_no_auth, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
