"""Tests for the Somfy config flow."""
import asyncio
from unittest.mock import Mock, patch

from pymfy.api.somfy_api import SomfyApi

from homeassistant import data_entry_flow
from homeassistant.components.somfy import config_flow, DOMAIN
from homeassistant.components.somfy.config_flow import register_flow_implementation
from tests.common import MockConfigEntry, mock_coro

CLIENT_SECRET_VALUE = "5678"

CLIENT_ID_VALUE = "1234"

AUTH_URL = "http://somfy.com"


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
    result = await flow.async_step_import()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"


async def test_full_flow(hass):
    """Check classic use case."""
    hass.data[DOMAIN] = {}
    register_flow_implementation(hass, CLIENT_ID_VALUE, CLIENT_SECRET_VALUE)
    flow = config_flow.SomfyFlowHandler()
    flow.hass = hass
    hass.config.api = Mock(base_url="https://example.com")
    flow._get_authorization_url = Mock(return_value=mock_coro((AUTH_URL, "state")))
    result = await flow.async_step_import()
    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["url"] == AUTH_URL
    result = await flow.async_step_auth("my_super_code")
    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP_DONE
    assert result["step_id"] == "creation"
    assert flow.code == "my_super_code"
    with patch.object(
        SomfyApi, "request_token", return_value={"access_token": "super_token"}
    ):
        result = await flow.async_step_creation()
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"]["refresh_args"] == {
        "client_id": CLIENT_ID_VALUE,
        "client_secret": CLIENT_SECRET_VALUE,
    }
    assert result["title"] == "Somfy"
    assert result["data"]["token"] == {"access_token": "super_token"}


async def test_abort_if_authorization_timeout(hass):
    """Check Somfy authorization timeout."""
    flow = config_flow.SomfyFlowHandler()
    flow.hass = hass
    flow._get_authorization_url = Mock(side_effect=asyncio.TimeoutError)
    result = await flow.async_step_auth()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "authorize_url_timeout"
