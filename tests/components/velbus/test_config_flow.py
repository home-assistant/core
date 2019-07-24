"""Tests for the Velbus config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.velbus import config_flow
from homeassistant.const import CONF_PORT, CONF_NAME

from tests.common import MockConfigEntry

PORT_SERIAL = '/dev/ttyACME100'
PORT_TCP = '127.0.1.0.1:3788'


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.VelbusConfigFlow()
    flow.hass = hass
    return flow


async def test_user(hass):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'

    result = await flow.async_step_user({
        CONF_NAME: 'Velbus Test Serial', CONF_PORT: PORT_SERIAL})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['errors'] == {'port': 'connection_failed'}

    result = await flow.async_step_user({
        CONF_NAME: 'Velbus Test TCP', CONF_PORT: PORT_TCP})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['errors'] == {'port': 'connection_failed'}


async def test_import(hass):
    """Test import step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import({CONF_PORT: PORT_TCP})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['errors'] == {'port': 'connection_failed'}


async def test_abort_if_already_setup(hass):
    """Test we abort if Daikin is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(domain='velbus',
                    data={CONF_PORT: PORT_TCP,
                          CONF_NAME: 'velbus home'}).add_to_hass(hass)

    result = await flow.async_step_import(
        {CONF_PORT: PORT_TCP, CONF_NAME: 'velbus import test'})
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'port_exists'

    result = await flow.async_step_user(
        {CONF_PORT: PORT_TCP, CONF_NAME: 'velbus import test'})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['errors'] == {'port': 'port_exists'}
