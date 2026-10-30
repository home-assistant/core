"""Test the Bosch Smart Camera config flow."""

import base64
from http import HTTPStatus
import json
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
)
from homeassistant.components.bosch_smart_camera.application_credentials import (
    OAUTH2_AUTHORIZE,
    OAUTH2_CLIENT_ID,
    OAUTH2_SCOPES,
    OAUTH2_TOKEN,
)
from homeassistant.components.bosch_smart_camera.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

REDIRECT_URI = "https://example.com/auth/external/callback"

ACCOUNT_ID = "fake-account-sub"


def _fake_access_token(claims: dict[str, object]) -> str:
    """Build an unsigned fake JWT access token from the given claims."""

    def _part(value: dict[str, object]) -> str:
        raw = json.dumps(value).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return ".".join([_part({"alg": "none"}), _part(claims), "sig"])


pytestmark = pytest.mark.usefixtures("current_request_with_host")


@pytest.fixture(autouse=True)
async def setup_application_credentials(hass: HomeAssistant) -> None:
    """Set up the application credentials component."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the OAuth2 flow creates an entry that loads and unloads."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    parsed = urlparse(result["url"])
    query = {key: value[0] for key, value in parse_qs(parsed.query).items()}
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == OAUTH2_AUTHORIZE
    assert query["client_id"] == OAUTH2_CLIENT_ID
    assert query["redirect_uri"] == REDIRECT_URI
    assert query["scope"] == OAUTH2_SCOPES
    assert query["code_challenge_method"] == "S256"

    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": _fake_access_token({"sub": ACCOUNT_ID}),
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bosch Smart Camera"
    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"]["token"]["access_token"] == _fake_access_token(
        {"sub": ACCOUNT_ID}
    )
    assert result["result"].unique_id == ACCOUNT_ID
    assert "code_verifier" in aioclient_mock.mock_calls[0][2]

    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_account_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the same account cannot be configured twice."""
    MockConfigEntry(domain=DOMAIN, unique_id=ACCOUNT_ID).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": _fake_access_token({"sub": ACCOUNT_ID}),
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "access_token",
    [
        _fake_access_token({"iss": "fake"}),
        "not-a-jwt",
        _fake_access_token({"sub": 123}),
        _fake_access_token({"sub": ""}),
        _fake_access_token({"sub": "   "}),
        _fake_access_token({"sub": ["a"]}),
        _fake_access_token({"sub": "a" * 129}),
    ],
    ids=[
        "missing_sub",
        "malformed",
        "int_sub",
        "empty_sub",
        "whitespace_sub",
        "list_sub",
        "too_long_sub",
    ],
)
async def test_invalid_token(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
) -> None:
    """Test a token without a usable subject aborts the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (BoschCameraAuthError, "invalid_auth"),
        (BoschCameraConnectionError, "cannot_connect"),
        (BoschCameraInvalidResponseError, "cannot_connect"),
    ],
)
async def test_api_access_checked_before_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_list_cameras: AsyncMock,
    error: type[Exception],
    reason: str,
) -> None:
    """Test the flow aborts when the camera API cannot be reached with the token."""
    mock_list_cameras.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": _fake_access_token({"sub": ACCOUNT_ID}),
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert not hass.config_entries.async_entries(DOMAIN)
