"""Tests for the Somfy config flow."""
import asyncio
import logging
from unittest.mock import patch

import pytest

from homeassistant import data_entry_flow, setup, config_entries
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import mock_platform

TEST_DOMAIN = "oauth2_test"
CLIENT_SECRET = "5678"
CLIENT_ID = "1234"
AUTHORIZE_URL = "https://example.como/auth/authorize"
TOKEN_URL = "https://example.como/auth/token"


@pytest.fixture
async def local_impl(hass):
    """Local implementation."""
    assert await setup.async_setup_component(hass, "http", {})
    return config_entry_oauth2_flow.LocalOAuth2Implementation(
        hass, TEST_DOMAIN, CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL
    )


@pytest.fixture
def flow_handler(hass):
    """Return a registered config flow."""

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    class TestFlowHandler(
        config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=TEST_DOMAIN
    ):
        """Test flow handler."""

        DOMAIN = TEST_DOMAIN

        @property
        def logger(self) -> logging.Logger:
            """Return logger."""
            return logging.getLogger(__name__)

    return TestFlowHandler


async def test_abort_if_no_implementation(hass, flow_handler):
    """Check flow abort when no implementations."""
    flow = flow_handler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "missing_configuration"


async def test_abort_if_authorization_timeout(hass, flow_handler, local_impl):
    """Check timeout generating authorization url."""
    flow_handler.async_register_implementation(hass, local_impl)

    flow = flow_handler()
    flow.hass = hass

    with patch.object(
        local_impl, "async_generate_authorize_url", side_effect=asyncio.TimeoutError
    ):
        result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "authorize_url_timeout"


async def test_full_flow(
    hass, flow_handler, local_impl, aiohttp_client, aioclient_mock
):
    """Check full flow."""
    hass.config.api.base_url = "https://example.com"
    flow_handler.async_register_implementation(hass, local_impl)

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(hass, {"flow_id": result["flow_id"]})

    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["url"] == (
        f"{AUTHORIZE_URL}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["data"]["implementation"] == TEST_DOMAIN

    result["data"]["token"].pop("expires_at")
    assert result["data"]["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }
