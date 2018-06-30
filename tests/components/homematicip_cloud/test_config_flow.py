"""Tests for HomematicIP Cloud config flow."""
from unittest.mock import Mock, patch

from homeassistant.components import homematicip_cloud as hmipc
from homeassistant.components.homematicip_cloud import (
    config_flow, const, errors)

from tests.common import MockConfigEntry, mock_coro


async def test_flow_works(hass, aioclient_mock):
    """Test config flow works."""
    home = Mock()
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    hap = hmipc.hap.HomematicipRegister(hass, config)
    with patch.object(hmipc.hap.HomematicipRegister, 'async_setup',
                      return_value=mock_coro(home)), \
        patch.object(hmipc.hap.HomematicipRegister, 'async_register',
                     return_value=mock_coro(home)):
        hap.authtoken = 'ABC'
        result = await flow.async_step_init(user_input=config)

        assert hap.authtoken == 'ABC'
        assert result['type'] == 'create_entry'


async def test_flow_init_connection_error(hass, aioclient_mock):
    """Test config flow init connection error."""
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    with patch.object(hmipc.hap.HomematicipRegister, 'async_setup',
                      side_effect=errors.HmipcConnectionError):
        result = await flow.async_step_init(user_input=config)
        assert result['type'] == 'abort'


async def test_flow_init_register_failed(hass, aioclient_mock):
    """Test config flow init registration failed."""
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    with patch.object(hmipc.hap.HomematicipRegister, 'async_setup',
                      side_effect=errors.HmipcRegistrationFailed):
        result = await flow.async_step_init(user_input=config)
        assert result['type'] == 'form'
        assert result['errors'] == {'base': 'register_failed'}


async def test_flow_link_connection_error(hass, aioclient_mock):
    """Test config flow link connection error."""
    home = Mock()
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    with patch.object(hmipc.hap.HomematicipRegister, 'async_setup',
                      return_value=mock_coro(home)), \
        patch.object(hmipc.hap.HomematicipRegister, 'async_register',
                     side_effect=errors.HmipcConnectionError):
        result = await flow.async_step_init(user_input=config)
        assert result['type'] == 'abort'


async def test_flow_link_press_button(hass, aioclient_mock):
    """Test config flow ask for pressing the blue button."""
    home = Mock()
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    with patch.object(hmipc.hap.HomematicipRegister, 'async_setup',
                      return_value=mock_coro(home)), \
        patch.object(hmipc.hap.HomematicipRegister, 'async_register',
                     side_effect=errors.HmipcPressButton):
        result = await flow.async_step_init(user_input=config)
        assert result['type'] == 'form'
        assert result['errors'] == {'base': 'press_the_button'}


async def test_init_flow_show_form(hass, aioclient_mock):
    """Test config flow ."""
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init(user_input=None)
    assert result['type'] == 'form'


async def test_init_already_configured(hass, aioclient_mock):
    """Test HAP is already configured."""
    MockConfigEntry(domain=const.DOMAIN, data={
        const.HMIPC_HAPID: 'ABC123',
    }).add_to_hass(hass)
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }

    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init(user_input=config)
    assert result['type'] == 'abort'


async def test_import_config(hass):
    """Test importing a host with an existing config file."""
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import({
        hmipc.HMIPC_HAPID: 'ABC123',
        hmipc.HMIPC_AUTHTOKEN: '123',
        hmipc.HMIPC_NAME: 'hmip'
    })

    assert result['type'] == 'create_entry'
    assert result['title'] == 'ABC123'
    assert result['data'] == {
        hmipc.HMIPC_HAPID: 'ABC123',
        hmipc.HMIPC_AUTHTOKEN: '123',
        hmipc.HMIPC_NAME: 'hmip'
    }


async def test_import_existing_config(hass):
    """Test importing a host with an existing config file."""
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    MockConfigEntry(domain=hmipc.DOMAIN, data={
        hmipc.HMIPC_HAPID: 'ABC123',
    }).add_to_hass(hass)

    result = await flow.async_step_import({
        hmipc.HMIPC_HAPID: 'ABC123',
        hmipc.HMIPC_AUTHTOKEN: '123',
        hmipc.HMIPC_NAME: 'hmip'
    })

    assert result['type'] == 'abort'
