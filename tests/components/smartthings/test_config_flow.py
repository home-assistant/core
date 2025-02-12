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

from tests.common import MockConfigEntry
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


@pytest.mark.usefixtures("current_request_with_host")
async def test_duplicate_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate entry is not able to set up."""
    mock_config_entry.add_to_hass(hass)
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauthentication(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_config_entry.data["token"].pop("expires_at")
    assert mock_config_entry.data[CONF_TOKEN] == {
        "refresh_token": "new-refresh-token",
        "access_token": "new-access-token",
        "token_type": "Bearer",
        "expires_in": 82806,
        "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
        "r:locations:* w:locations:* x:locations:* "
        "r:scenes:* x:scenes:* r:rules:* w:rules:* "
        "r:installedapps w:installedapps",
        "access_tier": 0,
        "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
    }


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication with different account."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* "
            "r:installedapps w:installedapps",
            "access_tier": 0,
            "installed_app_id": "123123123-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_account_mismatch"
