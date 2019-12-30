"""Define tests for the OpenUV config flow."""
from unittest.mock import patch

from pyopenuv.errors import OpenUvError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.openuv import DOMAIN, config_flow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)

from tests.common import MockConfigEntry, mock_coro


@pytest.fixture
def uv_index_response():
    """Define a fixture for a successful /uv response."""
    return mock_coro()


@pytest.fixture
def mock_pyopenuv(uv_index_response):
    """Mock the pyopenuv library."""
    with patch("homeassistant.components.openuv.config_flow.Client") as MockClient:
        MockClient().uv_index.return_value = uv_index_response
        yield MockClient


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_API_KEY: "12345abcde",
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.OpenUvFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {CONF_LATITUDE: "identifier_exists"}


@pytest.mark.parametrize("uv_index_response", [mock_coro(exception=OpenUvError)])
async def test_invalid_api_key(hass, mock_pyopenuv):
    """Test that an invalid API key throws an error."""
    conf = {
        CONF_API_KEY: "12345abcde",
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    flow = config_flow.OpenUvFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.OpenUvFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_import(hass, mock_pyopenuv):
    """Test that the import step works."""
    conf = {
        CONF_API_KEY: "12345abcde",
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    flow = config_flow.OpenUvFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(import_config=conf)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "39.128712, -104.9812612"
    assert result["data"] == {
        CONF_API_KEY: "12345abcde",
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }


async def test_step_user(hass, mock_pyopenuv):
    """Test that the user step works."""
    conf = {
        CONF_API_KEY: "12345abcde",
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    flow = config_flow.OpenUvFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "39.128712, -104.9812612"
    assert result["data"] == {
        CONF_API_KEY: "12345abcde",
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }
