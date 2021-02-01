"""Test the Honeywell Lyric config flow."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.http import CONF_BASE_URL, DOMAIN as DOMAIN_HTTP
from homeassistant.components.lyric import config_flow
from homeassistant.components.lyric.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.fixture()
async def mock_impl(hass):
    """Mock implementation."""
    await setup.async_setup_component(hass, "http", {})

    impl = config_entry_oauth2_flow.LocalOAuth2Implementation(
        hass,
        DOMAIN,
        CLIENT_ID,
        CLIENT_SECRET,
        OAUTH2_AUTHORIZE,
        OAUTH2_TOKEN,
    )
    config_flow.OAuth2FlowHandler.async_register_implementation(hass, impl)
    return impl


async def test_abort_if_no_configuration(hass):
    """Check flow abort when no configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = config_flow.OAuth2FlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "missing_configuration"


async def test_full_flow(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Check full flow."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_CLIENT_ID: CLIENT_ID,
                CONF_CLIENT_SECRET: CLIENT_SECRET,
            },
            DOMAIN_HTTP: {CONF_BASE_URL: "https://example.com"},
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
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch("homeassistant.components.lyric.api.ConfigEntryLyricClient"):
        with patch(
            "homeassistant.components.lyric.async_setup_entry", return_value=True
        ) as mock_setup:
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

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_abort_if_authorization_timeout(hass, mock_impl):
    """Check Somfy authorization timeout."""
    flow = config_flow.OAuth2FlowHandler()
    flow.hass = hass

    with patch.object(
        mock_impl, "async_generate_authorize_url", side_effect=asyncio.TimeoutError
    ):
        result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "authorize_url_timeout"
