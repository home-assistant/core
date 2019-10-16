"""Tests for the Somfy config flow."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant import data_entry_flow, setup, config_entries
from homeassistant.components.somfy import config_flow, DOMAIN, const, local_auth
from tests.common import MockConfigEntry

CLIENT_SECRET_VALUE = "5678"

CLIENT_ID_VALUE = "1234"

AUTH_URL = "http://somfy.com"


@pytest.fixture()
async def mock_impl(hass):
    """Mock implementation."""
    await setup.async_setup_component(hass, "http", {})
    impl = local_auth.LocalSomfyImplementation(
        hass, CLIENT_ID_VALUE, CLIENT_SECRET_VALUE
    )
    config_flow.register_flow_implementation(hass, impl)
    return impl


async def test_abort_if_no_configuration(hass):
    """Check flow abort when no configuration."""
    hass.data[DOMAIN] = {const.DATA_IMPLEMENTATION: {}}
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
    result = await flow.async_step_import()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"


async def test_full_flow(hass, aiohttp_client, requests_mock):
    """Check classic use case."""
    assert await setup.async_setup_component(
        hass,
        "somfy",
        {
            "somfy": {
                "client_id": CLIENT_ID_VALUE,
                "client_secret": CLIENT_SECRET_VALUE,
            },
            "http": {"base_url": "https://example.com"},
        },
    )

    result = await hass.config_entries.flow.async_init(
        "somfy", context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["url"] == (
        "https://accounts.somfy.com/oauth/oauth/v2/auth"
        f"?response_type=code&client_id={CLIENT_ID_VALUE}"
        "&redirect_uri=https%3A%2F%2Fexample.com%2Fauth%2Fsomfy%2Fcallback"
        f"&state={result['flow_id']}"
    )

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(f'/auth/somfy/callback?code=abcd&state={result["flow_id"]}')
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    requests_mock.post(
        "https://accounts.somfy.com/oauth/oauth/v2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.somfy.local_auth.LocalSomfyImplementation.async_create_api_auth"
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["data"]["implementation"] == "somfy"

    result["data"]["token"].pop("expires_at")
    assert result["data"]["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }

    assert "somfy" in hass.config.components
    entry = hass.config_entries.async_entries("somfy")[0]
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
