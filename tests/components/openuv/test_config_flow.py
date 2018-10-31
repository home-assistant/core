"""Define tests for the OpenUV config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.openuv import DOMAIN, config_flow
from homeassistant.const import (
    CONF_API_KEY, CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE)

from tests.common import MockConfigEntry, mock_coro


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_API_KEY: '12345abcde',
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.OpenUvFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['errors'] == {'base': 'identifier_exists'}


async def test_invalid_api_key(hass):
    """Test that an invalid API key throws an error."""
    conf = {
        CONF_API_KEY: '12345abcde',
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    flow = config_flow.OpenUvFlowHandler()
    flow.hass = hass

    with patch('pyopenuv.util.validate_api_key',
               return_value=mock_coro(False)):
        result = await flow.async_step_user(user_input=conf)
        assert result['errors'] == {'base': 'invalid_api_key'}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.OpenUvFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {
        CONF_API_KEY: '12345abcde',
    }

    flow = config_flow.OpenUvFlowHandler()
    flow.hass = hass

    with patch('pyopenuv.util.validate_api_key',
               return_value=mock_coro(True)):
        result = await flow.async_step_import(import_config=conf)

        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result['title'] == '{0}, {1}'.format(
            hass.config.latitude, hass.config.longitude)
        assert result['data'] == conf


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {
        CONF_API_KEY: '12345abcde',
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    flow = config_flow.OpenUvFlowHandler()
    flow.hass = hass

    with patch('pyopenuv.util.validate_api_key',
               return_value=mock_coro(True)):
        result = await flow.async_step_user(user_input=conf)

        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result['title'] == '{0}, {1}'.format(
            conf[CONF_LATITUDE], conf[CONF_LONGITUDE])
        assert result['data'] == conf
