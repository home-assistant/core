"""Tests for ZHA config flow."""
from homeassistant.components.zha import config_flow
from homeassistant.components.zha.const import DOMAIN, RadioType
from tests.common import MockConfigEntry


async def test_flow_works(hass):
    """Test that config flow works."""
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(
        user_input={'database_path': 'zigbee.db', 'usb_path': '/dev/ttyUSB1'})

    assert result['type'] == 'create_entry'
    assert result['title'] == '/dev/ttyUSB1'
    assert result['data'] == {
        'database_path': 'zigbee.db',
        'usb_path': '/dev/ttyUSB1'
    }


async def test_import(hass):
    """Test import from configuration.yaml ."""
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import({
        'usb_path': '/dev/ttyUSB1',
        'database_path': 'zigbee.db',
        'baudrate': 28800,
        'radio_type': RadioType.xbee,
        'device_config': {
            '01:23:45:67:89:ab:cd:ef-1': {
                'type': 'light'
            }
        }
    })

    assert result['type'] == 'create_entry'
    assert result['title'] == '/dev/ttyUSB1'
    assert result['data'] == {
        'database_path': 'zigbee.db',
        'usb_path': '/dev/ttyUSB1',
        'baudrate': 28800,
        'radio_type': 'xbee',
        'device_config': {
            '01:23:45:67:89:ab:cd:ef-1': {
                'type': 'light'
            }
        }
    }


async def test_flow_existing_config_entry(hass):
    """Test if config entry already exists."""
    MockConfigEntry(domain=DOMAIN, data={
        'usb_path': '/dev/ttyUSB1'
    }).add_to_hass(hass)
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()

    assert result['type'] == 'abort'
