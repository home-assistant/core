"""Tests for ZHA config flow."""
from asynctest import patch
from homeassistant.components.zha import config_flow
from homeassistant.components.zha.const import DOMAIN
from tests.common import MockConfigEntry


async def test_user_flow(hass):
    """Test that config flow works."""
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    with patch('homeassistant.components.zha.config_flow'
               '.check_zigpy_connection', return_value=False):
        result = await flow.async_step_user(
            user_input={'usb_path': '/dev/ttyUSB1', 'radio_type': 'ezsp'})

    assert result['errors'] == {'base': 'cannot_connect'}

    with patch('homeassistant.components.zha.config_flow'
               '.check_zigpy_connection', return_value=True):
        result = await flow.async_step_user(
            user_input={'usb_path': '/dev/ttyUSB1', 'radio_type': 'ezsp'})

    assert result['type'] == 'create_entry'
    assert result['title'] == '/dev/ttyUSB1'
    assert result['data'] == {
        'usb_path': '/dev/ttyUSB1',
        'radio_type': 'ezsp'
    }


async def test_user_flow_existing_config_entry(hass):
    """Test if config entry already exists."""
    MockConfigEntry(domain=DOMAIN, data={
        'usb_path': '/dev/ttyUSB1'
    }).add_to_hass(hass)
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()

    assert result['type'] == 'abort'


async def test_import_flow(hass):
    """Test import from configuration.yaml ."""
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import({
        'usb_path': '/dev/ttyUSB1',
        'radio_type': 'xbee',
    })

    assert result['type'] == 'create_entry'
    assert result['title'] == '/dev/ttyUSB1'
    assert result['data'] == {
        'usb_path': '/dev/ttyUSB1',
        'radio_type': 'xbee'
    }


async def test_import_flow_existing_config_entry(hass):
    """Test import from configuration.yaml ."""
    MockConfigEntry(domain=DOMAIN, data={
        'usb_path': '/dev/ttyUSB1'
    }).add_to_hass(hass)
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import({
        'usb_path': '/dev/ttyUSB1',
        'radio_type': 'xbee',
    })

    assert result['type'] == 'abort'
