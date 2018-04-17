"""Tests for deCONZ config flow."""
from unittest.mock import patch
import pytest

import voluptuous as vol
from homeassistant.components.deconz import config_flow
from tests.common import MockConfigEntry

import pydeconz


async def test_flow_works(hass, aioclient_mock):
    """Test that config flow works."""
    aioclient_mock.get(pydeconz.utils.URL_DISCOVER, json=[
        {'id': 'id', 'internalipaddress': '1.2.3.4', 'internalport': 80}
    ])
    aioclient_mock.post('http://1.2.3.4:80/api', json=[
        {"success": {"username": "1234567890ABCDEF"}}
    ])

    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass
    await flow.async_step_init()
    result = await flow.async_step_link(user_input={})

    assert result['type'] == 'create_entry'
    assert result['title'] == 'deCONZ-id'
    assert result['data'] == {
        'bridgeid': 'id',
        'host': '1.2.3.4',
        'port': 80,
        'api_key': '1234567890ABCDEF'
    }


async def test_flow_already_registered_bridge(hass):
    """Test config flow don't allow more than one bridge to be registered."""
    MockConfigEntry(domain='deconz', data={
        'host': '1.2.3.4'
    }).add_to_hass(hass)
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'abort'


async def test_flow_no_discovered_bridges(hass, aioclient_mock):
    """Test config flow discovers no bridges."""
    aioclient_mock.get(pydeconz.utils.URL_DISCOVER, json=[])
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'abort'


async def test_flow_one_bridge_discovered(hass, aioclient_mock):
    """Test config flow discovers one bridge."""
    aioclient_mock.get(pydeconz.utils.URL_DISCOVER, json=[
        {'id': 'id', 'internalipaddress': '1.2.3.4', 'internalport': 80}
    ])
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'form'
    assert result['step_id'] == 'link'


async def test_flow_two_bridges_discovered(hass, aioclient_mock):
    """Test config flow discovers two bridges."""
    aioclient_mock.get(pydeconz.utils.URL_DISCOVER, json=[
        {'id': 'id1', 'internalipaddress': '1.2.3.4', 'internalport': 80},
        {'id': 'id2', 'internalipaddress': '5.6.7.8', 'internalport': 80}
    ])
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'form'
    assert result['step_id'] == 'init'

    with pytest.raises(vol.Invalid):
        assert result['data_schema']({'host': '0.0.0.0'})

    result['data_schema']({'host': '1.2.3.4'})
    result['data_schema']({'host': '5.6.7.8'})


async def test_link_no_api_key(hass, aioclient_mock):
    """Test config flow should abort if no API key was possible to retrieve."""
    aioclient_mock.post('http://1.2.3.4:80/api', json=[])
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass
    flow.deconz_config = {'host': '1.2.3.4', 'port': 80}

    result = await flow.async_step_link(user_input={})
    assert result['type'] == 'form'
    assert result['step_id'] == 'link'
    assert result['errors'] == {'base': 'no_key'}


async def test_link_already_registered_bridge(hass):
    """Test that link verifies to only allow one config entry to complete.

    This is possible with discovery which will allow the user to complete
    a second config entry and then complete the discovered config entry.
    """
    MockConfigEntry(domain='deconz', data={
        'host': '1.2.3.4'
    }).add_to_hass(hass)
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass
    flow.deconz_config = {'host': '1.2.3.4', 'port': 80}

    result = await flow.async_step_link(user_input={})
    assert result['type'] == 'abort'


async def test_bridge_discovery(hass):
    """Test a bridge being discovered with no additional config file."""
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass
    with patch.object(config_flow, 'load_json', return_value={}):
        result = await flow.async_step_discovery({
            'host': '1.2.3.4',
            'port': 80,
            'serial': 'id'
        })

    assert result['type'] == 'form'
    assert result['step_id'] == 'link'


async def test_bridge_discovery_config_file(hass):
    """Test a bridge being discovered with a corresponding config file."""
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass
    with patch.object(config_flow, 'load_json',
                      return_value={'host': '1.2.3.4',
                                    'port': 8080,
                                    'api_key': '1234567890ABCDEF'}):
        result = await flow.async_step_discovery({
            'host': '1.2.3.4',
            'port': 80,
            'serial': 'id'
        })

    assert result['type'] == 'create_entry'
    assert result['title'] == 'deCONZ-id'
    assert result['data'] == {
        'bridgeid': 'id',
        'host': '1.2.3.4',
        'port': 80,
        'api_key': '1234567890ABCDEF'
    }


async def test_bridge_discovery_other_config_file(hass):
    """Test a bridge being discovered with another bridges config file."""
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass
    with patch.object(config_flow, 'load_json',
                      return_value={'host': '5.6.7.8', 'api_key': '5678'}):
        result = await flow.async_step_discovery({
            'host': '1.2.3.4',
            'port': 80,
            'serial': 'id'
        })

    assert result['type'] == 'form'
    assert result['step_id'] == 'link'


async def test_bridge_discovery_already_configured(hass):
    """Test if a discovered bridge has already been configured."""
    MockConfigEntry(domain='deconz', data={
        'host': '1.2.3.4'
    }).add_to_hass(hass)

    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery({
        'host': '1.2.3.4',
        'serial': 'id'
    })

    assert result['type'] == 'abort'


async def test_import_without_api_key(hass):
    """Test importing a host without an API key."""
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import({
        'host': '1.2.3.4',
    })

    assert result['type'] == 'form'
    assert result['step_id'] == 'link'


async def test_import_with_api_key(hass):
    """Test importing a host with an API key."""
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import({
        'bridgeid': 'id',
        'host': '1.2.3.4',
        'port': 80,
        'api_key': '1234567890ABCDEF'
    })

    assert result['type'] == 'create_entry'
    assert result['title'] == 'deCONZ-id'
    assert result['data'] == {
        'bridgeid': 'id',
        'host': '1.2.3.4',
        'port': 80,
        'api_key': '1234567890ABCDEF'
    }
