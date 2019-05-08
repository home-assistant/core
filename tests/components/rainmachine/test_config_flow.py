"""Define tests for the OpenUV config flow."""
from unittest.mock import patch

from regenmaschine import Client
from regenmaschine.errors import RainMachineError

from homeassistant import data_entry_flow
from homeassistant.components.rainmachine import DOMAIN, config_flow
from homeassistant.const import (
    CONF_EMAIL, CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SSL,
    CONF_SCAN_INTERVAL, CONF_TYPE)

from tests.common import MockConfigEntry, mock_coro


async def test_local_duplicate_error(hass):
    """Test that an error is shown when a local integration exists."""
    conf = {
        CONF_IP_ADDRESS: '192.168.1.100',
        CONF_PASSWORD: 'password',
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    result = await flow.async_step_local(user_input=conf)
    assert result['errors'] == {CONF_IP_ADDRESS: 'identifier_exists'}


async def test_local_invalid_creds(hass):
    """Test that invalid local credentials throw an error."""
    conf = {
        CONF_IP_ADDRESS: '192.168.1.100',
        CONF_PASSWORD: 'bad_password',
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    with patch.object(Client, 'load_local',
                      return_value=mock_coro(exception=RainMachineError)):
        result = await flow.async_step_local(user_input=conf)
        assert result['errors'] == {CONF_PASSWORD: 'invalid_credentials'}


async def test_remote_duplicate_error(hass):
    """Test that an error is shown when a remote integration exists."""
    conf = {
        CONF_EMAIL: 'user@host.com',
        CONF_PASSWORD: 'password',
    }

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    result = await flow.async_step_remote(user_input=conf)
    assert result['errors'] == {CONF_EMAIL: 'identifier_exists'}


async def test_remote_invalid_creds(hass):
    """Test that invalid remote credentials throw an error."""
    conf = {
        CONF_EMAIL: 'user@host.com',
        CONF_PASSWORD: 'bad_password',
    }

    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    with patch.object(Client, 'load_remote',
                      return_value=mock_coro(exception=RainMachineError)):
        result = await flow.async_step_remote(user_input=conf)
        assert result['errors'] == {CONF_PASSWORD: 'invalid_credentials'}


async def test_show_local_form(hass):
    """Test that the local form is chosen when its type is selected."""
    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(
        user_input={CONF_TYPE: 'Via IP Address'})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'local'


async def test_show_remote_form(hass):
    """Test that the remote form is chosen when its type is selected."""
    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(
        user_input={CONF_TYPE: 'Via RainMachine Cloud'})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'remote'


async def test_show_type_form(hass):
    """Test that the type-selection form is shown on first load."""
    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'


async def test_step_import_local(hass):
    """Test that the local import works."""
    conf = {
        CONF_IP_ADDRESS: '192.168.1.100',
        CONF_PASSWORD: 'password',
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    with patch.object(Client, 'load_local', return_value=mock_coro(True)):
        result = await flow.async_step_import(conf)

        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result['title'] == '192.168.1.100'
        assert result['data'] == {
            CONF_IP_ADDRESS: '192.168.1.100',
            CONF_PASSWORD: 'password',
            CONF_PORT: 8080,
            CONF_SSL: True,
            CONF_SCAN_INTERVAL: 60,
        }


async def test_step_import_remote(hass):
    """Test that the remote step works."""
    conf = {
        CONF_EMAIL: 'user@host.com',
        CONF_PASSWORD: 'password',
    }

    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    with patch.object(Client, 'load_remote', return_value=mock_coro(True)):
        result = await flow.async_step_import(conf)

        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result['title'] == 'user@host.com'
        assert result['data'] == {
            CONF_EMAIL: 'user@host.com',
            CONF_PASSWORD: 'password',
            CONF_SSL: True,
            CONF_SCAN_INTERVAL: 60,
        }


async def test_step_local(hass):
    """Test that the local step works."""
    conf = {
        CONF_IP_ADDRESS: '192.168.1.100',
        CONF_PASSWORD: 'password',
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    with patch.object(Client, 'load_local', return_value=mock_coro(True)):
        result = await flow.async_step_local(user_input=conf)

        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result['title'] == '192.168.1.100'
        assert result['data'] == {
            CONF_IP_ADDRESS: '192.168.1.100',
            CONF_PASSWORD: 'password',
            CONF_PORT: 8080,
            CONF_SSL: True,
            CONF_SCAN_INTERVAL: 60,
        }


async def test_step_remote(hass):
    """Test that the remote step works."""
    conf = {
        CONF_EMAIL: 'user@host.com',
        CONF_PASSWORD: 'password',
    }

    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass

    with patch.object(Client, 'load_remote', return_value=mock_coro(True)):
        result = await flow.async_step_remote(user_input=conf)

        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result['title'] == 'user@host.com'
        assert result['data'] == {
            CONF_EMAIL: 'user@host.com',
            CONF_PASSWORD: 'password',
            CONF_SSL: True,
            CONF_SCAN_INTERVAL: 60,
        }
