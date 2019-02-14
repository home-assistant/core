"""Define tests for the PlayStation 4 config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components import ps4
from homeassistant.components.ps4.const import (
    DEFAULT_NAME, DEFAULT_REGION)
from homeassistant.const import (
    CONF_CODE, CONF_HOST, CONF_IP_ADDRESS, CONF_NAME, CONF_REGION, CONF_TOKEN)

from tests.common import MockConfigEntry, mock_coro


MOCK_TITLE = 'PlayStation 4'
MOCK_CODE = '12345678'
MOCK_CREDS = '000aa000'
MOCK_HOST = '192.0.0.0'
MOCK_DEVICE = {
    CONF_HOST: MOCK_HOST,
    CONF_NAME: DEFAULT_NAME,
    CONF_REGION: DEFAULT_REGION
}
MOCK_CONFIG = {
    CONF_IP_ADDRESS: MOCK_HOST,
    CONF_NAME: DEFAULT_NAME,
    CONF_REGION: DEFAULT_REGION,
    CONF_CODE: MOCK_CODE
}
MOCK_DATA = {
    CONF_TOKEN: MOCK_CREDS,
    'devices': MOCK_DEVICE
}
MOCK_UDP_PORT = int(987)
MOCK_TCP_PORT = int(997)


async def test_full_flow_implementation(hass):
    """Test registering an implementation and flow works."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    # User Step Started, results in Step Creds
    with patch('pyps4_homeassistant.Helper.port_bind',
               return_value=mock_coro(return_value=None)):
        result = await flow.async_step_user()
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
        assert result['step_id'] == 'creds'

    # User input/submit results in Step Creds.
    result = await flow.async_step_creds()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'creds'

    # Step Creds results with form in Step Link.
    with patch('pyps4_homeassistant.Helper.get_creds',
               return_value=mock_coro(return_value=MOCK_CREDS)):
        result = await flow.async_step_creds('submit')
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
        assert result['step_id'] == 'link'

    # User Input results in created entry.
    with patch('pyps4_homeassistant.Helper.link',
               return_value=mock_coro(return_value=(True, True))), \
            patch('pyps4_homeassistant.Helper.has_devices',
                  return_value=mock_coro(return_value=[{'host-ip':
                                                        MOCK_HOST}])):
        result = await flow.async_step_link(MOCK_CONFIG)
        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result['data'][CONF_TOKEN] == MOCK_CREDS
        assert result['data']['devices'] == [MOCK_DEVICE]
        assert result['title'] == MOCK_TITLE


async def test_port_bind_pass(hass):
    """Test that flow continues if can bind to port."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    with patch('pyps4_homeassistant.Helper.port_bind',
               return_value=mock_coro(return_value=None)):
        result = await flow.async_step_user(user_input=None)
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
        assert result['step_id'] == 'creds'


async def test_port_bind_abort(hass):
    """Test that flow aborted when cannot bind to ports 987, 997."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    with patch('pyps4_homeassistant.Helper.port_bind',
               return_value=mock_coro(return_value=MOCK_UDP_PORT)):
        reason = 'port_987_bind_error'
        result = await flow.async_step_user(user_input=None)
        assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
        assert result['reason'] == reason

    with patch('pyps4_homeassistant.Helper.port_bind',
               return_value=mock_coro(return_value=MOCK_TCP_PORT)):
        reason = 'port_997_bind_error'
        result = await flow.async_step_user(user_input=None)
        assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
        assert result['reason'] == reason


async def test_duplicate_abort(hass):
    """Test that Flow aborts when already configured."""
    MockConfigEntry(domain=ps4.DOMAIN, data=MOCK_DATA).add_to_hass(hass)
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'devices_configured'


async def test_no_devices_found_abort(hass):
    """Test that failure to find devices aborts flow."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    with patch('pyps4_homeassistant.Helper.has_devices',
               return_value=mock_coro(return_value=None)):
        result = await flow.async_step_link(MOCK_CONFIG)
        assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
        assert result['reason'] == 'no_devices_found'


async def test_credential_abort(hass):
    """Test that failure to get credentials aborts flow."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    with patch('pyps4_homeassistant.Helper.get_creds',
               return_value=mock_coro(return_value=None)):
        result = await flow.async_step_creds('submit')
        assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
        assert result['reason'] == 'credential_error'


async def test_invalid_pin_error(hass):
    """Test that invalid pin throws an error."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    with patch('pyps4_homeassistant.Helper.link',
               return_value=mock_coro(return_value=(True, False))):
        result = await flow.async_step_link(MOCK_CONFIG)
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
        assert result['step_id'] == 'link'
        assert result['errors'] == {'base': 'login_failed'}


async def test_device_connection_error(hass):
    """Test that device not connected or on throws an error."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    with patch('pyps4_homeassistant.Helper.link',
               return_value=mock_coro(return_value=(False, True))):
        result = await flow.async_step_link(MOCK_CONFIG)
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
        assert result['step_id'] == 'link'
        assert result['errors'] == {'base': 'not_ready'}
