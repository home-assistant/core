"""Define tests for the PlayStation 4 config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components import ps4
from homeassistant.components.ps4.const import (
    DEFAULT_NAME, DEFAULT_REGION)
from homeassistant.const import (
    CONF_CODE, CONF_HOST, CONF_IP_ADDRESS, CONF_NAME, CONF_REGION, CONF_TOKEN)

from tests.common import MockConfigEntry

MOCK_TITLE = 'PlayStation 4'
MOCK_CODE = '12345678'
MOCK_CREDS = '000aa000'
MOCK_HOST = '192.0.0.0'
MOCK_HOST_ADDITIONAL = '192.0.0.1'
MOCK_DEVICE = {
    CONF_HOST: MOCK_HOST,
    CONF_NAME: DEFAULT_NAME,
    CONF_REGION: DEFAULT_REGION
}
MOCK_DEVICE_ADDITIONAL = {
    CONF_HOST: MOCK_HOST_ADDITIONAL,
    CONF_NAME: DEFAULT_NAME,
    CONF_REGION: DEFAULT_REGION
}
MOCK_CONFIG = {
    CONF_IP_ADDRESS: MOCK_HOST,
    CONF_NAME: DEFAULT_NAME,
    CONF_REGION: DEFAULT_REGION,
    CONF_CODE: MOCK_CODE
}
MOCK_CONFIG_ADDITIONAL = {
    CONF_IP_ADDRESS: MOCK_HOST_ADDITIONAL,
    CONF_NAME: DEFAULT_NAME,
    CONF_REGION: DEFAULT_REGION,
    CONF_CODE: MOCK_CODE
}
MOCK_DATA = {
    CONF_TOKEN: MOCK_CREDS,
    'devices': [MOCK_DEVICE]
}
MOCK_UDP_PORT = int(987)
MOCK_TCP_PORT = int(997)

MOCK_AUTO = {"Config Mode": 'Auto Discover'}
MOCK_MANUAL = {"Config Mode": 'Manual Entry', CONF_IP_ADDRESS: MOCK_HOST}


async def test_full_flow_implementation(hass):
    """Test registering an implementation and flow works."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass
    manager = hass.config_entries

    # User Step Started, results in Step Creds
    with patch('pyps4_homeassistant.Helper.port_bind',
               return_value=None):
        result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'creds'

    # Step Creds results with form in Step Mode.
    with patch('pyps4_homeassistant.Helper.get_creds',
               return_value=MOCK_CREDS):
        result = await flow.async_step_creds({})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'mode'

    # Step Mode with User Input which is not manual, results in Step Link.
    with patch('pyps4_homeassistant.Helper.has_devices',
               return_value=[{'host-ip': MOCK_HOST}]):
        result = await flow.async_step_mode(MOCK_AUTO)
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'link'

    # User Input results in created entry.
    with patch('pyps4_homeassistant.Helper.link',
               return_value=(True, True)), \
            patch('pyps4_homeassistant.Helper.has_devices',
                  return_value=[{'host-ip': MOCK_HOST}]):
        result = await flow.async_step_link(MOCK_CONFIG)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['data'][CONF_TOKEN] == MOCK_CREDS
    assert result['data']['devices'] == [MOCK_DEVICE]
    assert result['title'] == MOCK_TITLE

    await hass.async_block_till_done()

    # Add entry using result data.
    mock_data = {
        CONF_TOKEN: result['data'][CONF_TOKEN],
        'devices': result['data']['devices']}
    entry = MockConfigEntry(domain=ps4.DOMAIN, data=mock_data)
    entry.add_to_manager(manager)

    # Check if entry exists.
    assert len(manager.async_entries()) == 1
    # Check if there is a device config in entry.
    assert len(entry.data['devices']) == 1


async def test_multiple_flow_implementation(hass):
    """Test multiple device flows."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass
    manager = hass.config_entries

    # User Step Started, results in Step Creds
    with patch('pyps4_homeassistant.Helper.port_bind',
               return_value=None):
        result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'creds'

    # Step Creds results with form in Step Mode.
    with patch('pyps4_homeassistant.Helper.get_creds',
               return_value=MOCK_CREDS):
        result = await flow.async_step_creds({})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'mode'

    # Step Mode with User Input which is not manual, results in Step Link.
    with patch('pyps4_homeassistant.Helper.has_devices',
               return_value=[{'host-ip': MOCK_HOST},
                             {'host-ip': MOCK_HOST_ADDITIONAL}]):
        result = await flow.async_step_mode(MOCK_AUTO)
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'link'

    # User Input results in created entry.
    with patch('pyps4_homeassistant.Helper.link',
               return_value=(True, True)), \
            patch('pyps4_homeassistant.Helper.has_devices',
                  return_value=[{'host-ip': MOCK_HOST},
                                {'host-ip': MOCK_HOST_ADDITIONAL}]):
        result = await flow.async_step_link(MOCK_CONFIG)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['data'][CONF_TOKEN] == MOCK_CREDS
    assert result['data']['devices'] == [MOCK_DEVICE]
    assert result['title'] == MOCK_TITLE

    await hass.async_block_till_done()

    # Add entry using result data.
    mock_data = {
        CONF_TOKEN: result['data'][CONF_TOKEN],
        'devices': result['data']['devices']}
    entry = MockConfigEntry(domain=ps4.DOMAIN, data=mock_data)
    entry.add_to_manager(manager)

    # Check if entry exists.
    assert len(manager.async_entries()) == 1
    # Check if there is a device config in entry.
    assert len(entry.data['devices']) == 1

    # Test additional flow.

    # User Step Started, results in Step Mode:
    with patch('pyps4_homeassistant.Helper.port_bind',
               return_value=None), \
            patch('pyps4_homeassistant.Helper.has_devices',
                  return_value=[{'host-ip': MOCK_HOST},
                                {'host-ip': MOCK_HOST_ADDITIONAL}]):
        result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'mode'

    # Step Mode with User Input which is not manual, results in Step Link.
    with patch('pyps4_homeassistant.Helper.has_devices',
               return_value=[{'host-ip': MOCK_HOST},
                             {'host-ip': MOCK_HOST_ADDITIONAL}]):
        result = await flow.async_step_mode(MOCK_AUTO)
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'link'

    # Step Link
    with patch('pyps4_homeassistant.Helper.has_devices',
               return_value=[{'host-ip': MOCK_HOST},
                             {'host-ip': MOCK_HOST_ADDITIONAL}]), \
            patch('pyps4_homeassistant.Helper.link',
                  return_value=(True, True)):
        result = await flow.async_step_link(MOCK_CONFIG_ADDITIONAL)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['data'][CONF_TOKEN] == MOCK_CREDS
    assert len(result['data']['devices']) == 1
    assert result['title'] == MOCK_TITLE

    await hass.async_block_till_done()

    mock_data = {
        CONF_TOKEN: result['data'][CONF_TOKEN],
        'devices': result['data']['devices']}

    # Update config entries with result data
    entry = MockConfigEntry(domain=ps4.DOMAIN, data=mock_data)
    entry.add_to_manager(manager)
    manager.async_update_entry(entry)

    # Check if there are 2 entries.
    assert len(manager.async_entries()) == 2
    # Check if there is device config in entry.
    assert len(entry.data['devices']) == 1


async def test_port_bind_abort(hass):
    """Test that flow aborted when cannot bind to ports 987, 997."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    with patch('pyps4_homeassistant.Helper.port_bind',
               return_value=MOCK_UDP_PORT):
        reason = 'port_987_bind_error'
        result = await flow.async_step_user(user_input=None)
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == reason

    with patch('pyps4_homeassistant.Helper.port_bind',
               return_value=MOCK_TCP_PORT):
        reason = 'port_997_bind_error'
        result = await flow.async_step_user(user_input=None)
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == reason


async def test_duplicate_abort(hass):
    """Test that Flow aborts when found devices already configured."""
    MockConfigEntry(domain=ps4.DOMAIN, data=MOCK_DATA).add_to_hass(hass)
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    with patch('pyps4_homeassistant.Helper.has_devices',
               return_value=[{'host-ip': MOCK_HOST}]):
        result = await flow.async_step_link(user_input=None)
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'devices_configured'


async def test_additional_device(hass):
    """Test that Flow can configure another device."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass
    flow.creds = MOCK_CREDS
    manager = hass.config_entries

    # Mock existing entry.
    entry = MockConfigEntry(domain=ps4.DOMAIN, data=MOCK_DATA)
    entry.add_to_manager(manager)
    # Check that only 1 entry exists
    assert len(manager.async_entries()) == 1

    with patch('pyps4_homeassistant.Helper.has_devices',
               return_value=[{'host-ip': MOCK_HOST},
                             {'host-ip': MOCK_HOST_ADDITIONAL}]), \
            patch('pyps4_homeassistant.Helper.link',
                  return_value=(True, True)):
        result = await flow.async_step_link(MOCK_CONFIG_ADDITIONAL)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['data'][CONF_TOKEN] == MOCK_CREDS
    assert len(result['data']['devices']) == 1
    assert result['title'] == MOCK_TITLE

    # Add New Entry
    entry = MockConfigEntry(domain=ps4.DOMAIN, data=MOCK_DATA)
    entry.add_to_manager(manager)

    # Check that there are 2 entries
    assert len(manager.async_entries()) == 2


async def test_no_devices_found_abort(hass):
    """Test that failure to find devices aborts flow."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    with patch('pyps4_homeassistant.Helper.has_devices', return_value=[]):
        result = await flow.async_step_link()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'no_devices_found'


async def test_manual_mode(hass):
    """Test host specified in manual mode is passed to Step Link."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    # Step Mode with User Input: manual, results in Step Link.
    with patch('pyps4_homeassistant.Helper.has_devices',
               return_value=[{'host-ip': flow.m_device}]):
        result = await flow.async_step_mode(MOCK_MANUAL)
    assert flow.m_device == MOCK_HOST
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'link'


async def test_credential_abort(hass):
    """Test that failure to get credentials aborts flow."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    with patch('pyps4_homeassistant.Helper.get_creds', return_value=None):
        result = await flow.async_step_creds({})
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'credential_error'


async def test_wrong_pin_error(hass):
    """Test that incorrect pin throws an error."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    with patch('pyps4_homeassistant.Helper.link',
               return_value=(True, False)), \
            patch('pyps4_homeassistant.Helper.has_devices',
                  return_value=[{'host-ip': MOCK_HOST}]):
        result = await flow.async_step_link(MOCK_CONFIG)
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'link'
    assert result['errors'] == {'base': 'login_failed'}


async def test_device_connection_error(hass):
    """Test that device not connected or on throws an error."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    with patch('pyps4_homeassistant.Helper.link',
               return_value=(False, True)), \
            patch('pyps4_homeassistant.Helper.has_devices',
                  return_value=[{'host-ip': MOCK_HOST}]):
        result = await flow.async_step_link(MOCK_CONFIG)
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'link'
    assert result['errors'] == {'base': 'not_ready'}


async def test_manual_mode_no_ip_error(hass):
    """Test no IP specified in manual mode throws an error."""
    flow = ps4.PlayStation4FlowHandler()
    flow.hass = hass

    mock_input = {"Config Mode": 'Manual Entry'}

    result = await flow.async_step_mode(mock_input)
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'mode'
    assert result['errors'] == {CONF_IP_ADDRESS: 'no_ipaddress'}
