"""Tests for HomematicIP Cloud config flow."""
from unittest.mock import patch

from homeassistant.components.homematicip_cloud import hap as hmipc
from homeassistant.components.homematicip_cloud import config_flow, const

from tests.common import MockConfigEntry, mock_coro


async def test_flow_works(hass):
    """Test config flow works."""
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    hap = hmipc.HomematicipAuth(hass, config)
    with patch.object(hap, 'get_auth', return_value=mock_coro()), \
            patch.object(hmipc.HomematicipAuth, 'async_checkbutton',
                         return_value=mock_coro(True)), \
            patch.object(hmipc.HomematicipAuth, 'async_setup',
                         return_value=mock_coro(True)), \
            patch.object(hmipc.HomematicipAuth, 'async_register',
                         return_value=mock_coro(True)):
        hap.authtoken = 'ABC'
        result = await flow.async_step_init(user_input=config)

        assert hap.authtoken == 'ABC'
        assert result['type'] == 'create_entry'


async def test_flow_init_connection_error(hass):
    """Test config flow with accesspoint connection error."""
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    with patch.object(hmipc.HomematicipAuth, 'async_setup',
                      return_value=mock_coro(False)):
        result = await flow.async_step_init(user_input=config)
        assert result['type'] == 'form'


async def test_flow_link_connection_error(hass):
    """Test config flow client registration connection error."""
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    with patch.object(hmipc.HomematicipAuth, 'async_setup',
                      return_value=mock_coro(True)), \
        patch.object(hmipc.HomematicipAuth, 'async_checkbutton',
                     return_value=mock_coro(True)), \
        patch.object(hmipc.HomematicipAuth, 'async_register',
                     return_value=mock_coro(False)):
        result = await flow.async_step_init(user_input=config)
        assert result['type'] == 'abort'


async def test_flow_link_press_button(hass):
    """Test config flow ask for pressing the blue button."""
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    with patch.object(hmipc.HomematicipAuth, 'async_setup',
                      return_value=mock_coro(True)), \
        patch.object(hmipc.HomematicipAuth, 'async_checkbutton',
                     return_value=mock_coro(False)):
        result = await flow.async_step_init(user_input=config)
        assert result['type'] == 'form'
        assert result['errors'] == {'base': 'press_the_button'}


async def test_init_flow_show_form(hass):
    """Test config flow shows up with a form."""
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init(user_input=None)
    assert result['type'] == 'form'


async def test_init_already_configured(hass):
    """Test accesspoint is already configured."""
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
    """Test abort of an existing accesspoint from config."""
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    MockConfigEntry(domain=const.DOMAIN, data={
        hmipc.HMIPC_HAPID: 'ABC123',
    }).add_to_hass(hass)

    result = await flow.async_step_import({
        hmipc.HMIPC_HAPID: 'ABC123',
        hmipc.HMIPC_AUTHTOKEN: '123',
        hmipc.HMIPC_NAME: 'hmip'
    })

    assert result['type'] == 'abort'
