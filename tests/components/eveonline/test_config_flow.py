"""Test the Eve Online config flow."""

import base64
import json
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.eveonline.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    SCOPES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
CHARACTER_ID = 95465499
CHARACTER_NAME = "CCP Bartender"


def _make_jwt(character_id: int, character_name: str) -> str:
    """Create a fake Eve SSO JWT token."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=")
    payload_data = {
        "sub": f"CHARACTER:EVE:{character_id}",
        "name": character_name,
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=")
    signature = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}.{signature.decode()}"


async def _setup_credentials(hass: HomeAssistant) -> None:
    """Set up application credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check full OAuth2 flow."""
    await _setup_credentials(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    scope = "+".join(SCOPES)
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        f"&scope={scope}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    fake_jwt = _make_jwt(CHARACTER_ID, CHARACTER_NAME)

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": fake_jwt,
            "type": "Bearer",
            "expires_in": 1200,
        },
    )

    with patch(
        "homeassistant.components.eveonline.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == str(CHARACTER_ID)
    assert entry.title == CHARACTER_NAME
    assert entry.data["character_id"] == CHARACTER_ID
    assert entry.data["character_name"] == CHARACTER_NAME


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_rejects_duplicate_character(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check that adding the same character twice is rejected."""
    await _setup_credentials(hass)

    # First flow — should succeed.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    fake_jwt = _make_jwt(CHARACTER_ID, CHARACTER_NAME)
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": fake_jwt,
            "type": "Bearer",
            "expires_in": 1200,
        },
    )

    with patch(
        "homeassistant.components.eveonline.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    # Second flow — same character, should abort.
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state2 = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result2["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    await client.get(f"/auth/external/callback?code=abcd&state={state2}")

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token-2",
            "access_token": fake_jwt,
            "type": "Bearer",
            "expires_in": 1200,
        },
    )

    result2 = await hass.config_entries.flow.async_configure(result2["flow_id"])

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
