"""Tests for the Heos config flow module."""
import asyncio

from homeassistant import data_entry_flow
from homeassistant.components.heos.config_flow import HeosFlowHandler
from homeassistant.const import CONF_HOST


async def test_flow_aborts_already_setup(hass, config_entry):
    """Test flow aborts when entry already setup."""
    config_entry.add_to_hass(hass)
    flow = HeosFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_setup'


async def test_no_host_shows_form(hass):
    """Test form is shown when host not provided."""
    flow = HeosFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['errors'] == {}


async def test_cannot_connect_shows_error_form(hass, controller):
    """Test form is shown with error when cannot connect."""
    flow = HeosFlowHandler()
    flow.hass = hass

    errors = [ConnectionError, asyncio.TimeoutError]
    for error in errors:
        controller.connect.side_effect = error
        result = await flow.async_step_user({CONF_HOST: '127.0.0.1'})
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
        assert result['step_id'] == 'user'
        assert result['errors'][CONF_HOST] == 'connection_failure'
        assert controller.connect.call_count == 1
        assert controller.disconnect.call_count == 1
        controller.connect.reset_mock()
        controller.disconnect.reset_mock()


async def test_create_entry_when_host_valid(hass, controller):
    """Test result type is create entry when host is valid."""
    flow = HeosFlowHandler()
    flow.hass = hass
    data = {CONF_HOST: '127.0.0.1'}
    result = await flow.async_step_user(data)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == 'Controller (127.0.0.1)'
    assert result['data'] == data
    assert controller.connect.call_count == 1
    assert controller.disconnect.call_count == 1


async def test_create_entry_with_discovery(hass, controller):
    """Test result type is create entry when valid through discovery."""
    flow = HeosFlowHandler()
    flow.hass = hass
    data = {
        'host': '127.0.0.1',
        'manufacturer': 'Denon',
        'model_name': 'HEOS Drive',
        'model_number': 'DWSA-10 4.0',
        'name': 'Office',
        'port': 60006,
        'serial': None,
        'ssdp_description':
            'http://127.0.0.1:60006/upnp/desc/aios_device/aios_device.xml',
        'udn': 'uuid:e61de70c-2250-1c22-0080-0005cdf512be',
        'upnp_device_type': 'urn:schemas-denon-com:device:AiosDevice:1'
    }
    result = await flow.async_step_discovery(data)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == 'Controller (127.0.0.1)'
    assert result['data'] == {'host': '127.0.0.1'}
    assert controller.connect.call_count == 1
    assert controller.disconnect.call_count == 1
