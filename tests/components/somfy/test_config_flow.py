"""Tests for the Somfy config flow."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.somfy import DOMAIN, config_flow
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry

CLIENT_ID_VALUE = "1234"
CLIENT_SECRET_VALUE = "5678"


@pytest.fixture()
async def mock_impl(hass):
    """Mock implementation."""
    await setup.async_setup_component(hass, "http", {})

    impl = config_entry_oauth2_flow.LocalOAuth2Implementation(
        hass,
        DOMAIN,
        CLIENT_ID_VALUE,
        CLIENT_SECRET_VALUE,
        "https://accounts.somfy.com/oauth/oauth/v2/auth",
        "https://accounts.somfy.com/oauth/oauth/v2/token",
    )
    config_flow.SomfyFlowHandler.async_register_implementation(hass, impl)
    return impl


async def test_abort_if_no_configuration(hass):
    """Check flow abort when no configuration."""
    flow = config_flow.SomfyFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "missing_configuration"


async def test_abort_if_existing_entry(hass):
    """Check flow abort when an entry already exist."""
    flow = config_flow.SomfyFlowHandler()
    flow.hass = hass
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_full_flow(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Check full flow."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_CLIENT_ID: CLIENT_ID_VALUE,
                CONF_CLIENT_SECRET: CLIENT_SECRET_VALUE,
            },
            "http": {"base_url": "https://example.com"},
        },
    )

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

    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["url"] == (
        "https://accounts.somfy.com/oauth/oauth/v2/auth"
        f"?response_type=code&client_id={CLIENT_ID_VALUE}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        "https://accounts.somfy.com/oauth/oauth/v2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch("homeassistant.components.somfy.api.ConfigEntrySomfyApi"):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["data"]["auth_implementation"] == DOMAIN

    result["data"]["token"].pop("expires_at")
    assert result["data"]["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }

    assert DOMAIN in hass.config.components
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state == config_entries.ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED


async def test_abort_if_authorization_timeout(hass, mock_impl):
    """Check Somfy authorization timeout."""
    flow = config_flow.SomfyFlowHandler()
    flow.hass = hass

    with patch.object(
        mock_impl, "async_generate_authorize_url", side_effect=asyncio.TimeoutError
    ):
        result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "authorize_url_timeout"
