"""Tests for the SmartThings config flow module."""

from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.smartthings.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Check a full flow."""
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
        "https://api.smartthings.com/oauth/authorize"
        "?response_type=code&client_id=CLIENT_ID"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=r:devices:*+w:devices:*+x:devices:*+r:hubs:*+"
        "r:locations:*+w:locations:*+x:locations:*+r:scenes:*+"
        "x:scenes:*+r:rules:*+w:rules:*+r:installedapps+w:installedapps"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* "
            "r:installedapps w:installedapps",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1, result

    assert result["type"] is FlowResultType.CREATE_ENTRY
    result["data"]["token"].pop("expires_at")
    assert result["data"][CONF_TOKEN] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "token_type": "Bearer",
        "expires_in": 82806,
        "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
        "r:locations:* w:locations:* x:locations:* "
        "r:scenes:* x:scenes:* r:rules:* w:rules:* "
        "r:installedapps w:installedapps",
        "access_tier": 0,
        "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
    }
    assert result["result"].unique_id == "5aaaa925-2be1-4e40-b257-e4ef59083324"
