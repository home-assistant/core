"""Define tests for the OpenUV config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.rainmachine import DOMAIN, config_flow
from homeassistant.const import (
    CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SSL, CONF_SCAN_INTERVAL)

from tests.common import MockConfigEntry, mock_coro


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_IP_ADDRESS: '192.168.1.100',
        CONF_PASSWORD: 'password',
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['errors'] == {CONF_IP_ADDRESS: 'identifier_exists'}


async def test_invalid_password(hass):
    """Test that an invalid password throws an error."""
    from regenmaschine.errors import RainMachineError

    conf = {
        CONF_IP_ADDRESS: '192.168.1.100',
        CONF_PASSWORD: 'bad_password',
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    with patch('regenmaschine.login',
               return_value=mock_coro(exception=RainMachineError)):
        result = await flow.async_step_user(user_input=conf)
        assert result['errors'] == {CONF_PASSWORD: 'invalid_credentials'}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {
        CONF_IP_ADDRESS: '192.168.1.100',
        CONF_PASSWORD: 'password',
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    with patch('regenmaschine.login', return_value=mock_coro(True)):
        result = await flow.async_step_import(import_config=conf)

        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result['title'] == '192.168.1.100'
        assert result['data'] == {
            CONF_IP_ADDRESS: '192.168.1.100',
            CONF_PASSWORD: 'password',
            CONF_PORT: 8080,
            CONF_SSL: True,
            CONF_SCAN_INTERVAL: 60,
        }


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {
        CONF_IP_ADDRESS: '192.168.1.100',
        CONF_PASSWORD: 'password',
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    with patch('regenmaschine.login', return_value=mock_coro(True)):
        result = await flow.async_step_user(user_input=conf)

        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result['title'] == '192.168.1.100'
        assert result['data'] == {
            CONF_IP_ADDRESS: '192.168.1.100',
            CONF_PASSWORD: 'password',
            CONF_PORT: 8080,
            CONF_SSL: True,
            CONF_SCAN_INTERVAL: 60,
        }
