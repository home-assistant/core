"""Tests for Philips Hue config flow."""
import asyncio
from unittest.mock import Mock, patch

import aiohue
import pytest
import voluptuous as vol

from homeassistant.components.hue import config_flow, const, errors

from tests.common import MockConfigEntry, mock_coro


async def test_flow_works(hass, aioclient_mock):
    """Test config flow ."""
    aioclient_mock.get(const.API_NUPNP, json=[
        {'internalipaddress': '1.2.3.4', 'id': 'bla'}
    ])

    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    await flow.async_step_init()

    with patch('aiohue.Bridge') as mock_bridge:
        def mock_constructor(host, websession, username=None):
            """Fake the bridge constructor."""
            mock_bridge.host = host
            return mock_bridge

        mock_bridge.side_effect = mock_constructor
        mock_bridge.username = 'username-abc'
        mock_bridge.config.name = 'Mock Bridge'
        mock_bridge.config.bridgeid = 'bridge-id-1234'
        mock_bridge.create_user.return_value = mock_coro()
        mock_bridge.initialize.return_value = mock_coro()

        result = await flow.async_step_link(user_input={})

    assert mock_bridge.host == '1.2.3.4'
    assert len(mock_bridge.create_user.mock_calls) == 1
    assert len(mock_bridge.initialize.mock_calls) == 1

    assert result['type'] == 'create_entry'
    assert result['title'] == 'Mock Bridge'
    assert result['data'] == {
        'host': '1.2.3.4',
        'bridge_id': 'bridge-id-1234',
        'username': 'username-abc'
    }


async def test_flow_no_discovered_bridges(hass, aioclient_mock):
    """Test config flow discovers no bridges."""
    aioclient_mock.get(const.API_NUPNP, json=[])
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'abort'


async def test_flow_all_discovered_bridges_exist(hass, aioclient_mock):
    """Test config flow discovers only already configured bridges."""
    aioclient_mock.get(const.API_NUPNP, json=[
        {'internalipaddress': '1.2.3.4', 'id': 'bla'}
    ])
    MockConfigEntry(domain='hue', data={
        'host': '1.2.3.4'
    }).add_to_hass(hass)
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'abort'


async def test_flow_one_bridge_discovered(hass, aioclient_mock):
    """Test config flow discovers one bridge."""
    aioclient_mock.get(const.API_NUPNP, json=[
        {'internalipaddress': '1.2.3.4', 'id': 'bla'}
    ])
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'form'
    assert result['step_id'] == 'link'


async def test_flow_two_bridges_discovered(hass, aioclient_mock):
    """Test config flow discovers two bridges."""
    aioclient_mock.get(const.API_NUPNP, json=[
        {'internalipaddress': '1.2.3.4', 'id': 'bla'},
        {'internalipaddress': '5.6.7.8', 'id': 'beer'}
    ])
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'form'
    assert result['step_id'] == 'init'

    with pytest.raises(vol.Invalid):
        assert result['data_schema']({'host': '0.0.0.0'})

    result['data_schema']({'host': '1.2.3.4'})
    result['data_schema']({'host': '5.6.7.8'})


async def test_flow_two_bridges_discovered_one_new(hass, aioclient_mock):
    """Test config flow discovers two bridges."""
    aioclient_mock.get(const.API_NUPNP, json=[
        {'internalipaddress': '1.2.3.4', 'id': 'bla'},
        {'internalipaddress': '5.6.7.8', 'id': 'beer'}
    ])
    MockConfigEntry(domain='hue', data={
        'host': '1.2.3.4'
    }).add_to_hass(hass)
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'form'
    assert result['step_id'] == 'link'
    assert flow.host == '5.6.7.8'


async def test_flow_timeout_discovery(hass):
    """Test config flow ."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    with patch('aiohue.discovery.discover_nupnp',
               side_effect=asyncio.TimeoutError):
        result = await flow.async_step_init()

    assert result['type'] == 'abort'


async def test_flow_link_timeout(hass):
    """Test config flow ."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    with patch('aiohue.Bridge.create_user',
               side_effect=asyncio.TimeoutError):
        result = await flow.async_step_link({})

    assert result['type'] == 'form'
    assert result['step_id'] == 'link'
    assert result['errors'] == {
        'base': 'linking'
    }


async def test_flow_link_button_not_pressed(hass):
    """Test config flow ."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    with patch('aiohue.Bridge.create_user',
               side_effect=aiohue.LinkButtonNotPressed):
        result = await flow.async_step_link({})

    assert result['type'] == 'form'
    assert result['step_id'] == 'link'
    assert result['errors'] == {
        'base': 'register_failed'
    }


async def test_flow_link_unknown_host(hass):
    """Test config flow ."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    with patch('aiohue.Bridge.create_user',
               side_effect=aiohue.RequestError):
        result = await flow.async_step_link({})

    assert result['type'] == 'form'
    assert result['step_id'] == 'link'
    assert result['errors'] == {
        'base': 'linking'
    }


async def test_bridge_discovery(hass):
    """Test a bridge being discovered."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    with patch.object(config_flow, 'get_bridge',
                      side_effect=errors.AuthenticationRequired):
        result = await flow.async_step_discovery({
            'host': '0.0.0.0',
            'serial': '1234'
        })

    assert result['type'] == 'form'
    assert result['step_id'] == 'link'


async def test_bridge_discovery_emulated_hue(hass):
    """Test if discovery info is from an emulated hue instance."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery({
        'name': 'HASS Bridge',
        'host': '0.0.0.0',
        'serial': '1234'
    })

    assert result['type'] == 'abort'


async def test_bridge_discovery_already_configured(hass):
    """Test if a discovered bridge has already been configured."""
    MockConfigEntry(domain='hue', data={
        'host': '0.0.0.0'
    }).add_to_hass(hass)

    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery({
        'host': '0.0.0.0',
        'serial': '1234'
    })

    assert result['type'] == 'abort'


async def test_import_with_existing_config(hass):
    """Test importing a host with an existing config file."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    bridge = Mock()
    bridge.username = 'username-abc'
    bridge.config.bridgeid = 'bridge-id-1234'
    bridge.config.name = 'Mock Bridge'
    bridge.host = '0.0.0.0'

    with patch.object(config_flow, '_find_username_from_config',
                      return_value='mock-user'), \
            patch.object(config_flow, 'get_bridge',
                         return_value=mock_coro(bridge)):
        result = await flow.async_step_import({
            'host': '0.0.0.0',
            'path': 'bla.conf'
        })

    assert result['type'] == 'create_entry'
    assert result['title'] == 'Mock Bridge'
    assert result['data'] == {
        'host': '0.0.0.0',
        'bridge_id': 'bridge-id-1234',
        'username': 'username-abc'
    }


async def test_import_with_no_config(hass):
    """Test importing a host without an existing config file."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    with patch.object(config_flow, 'get_bridge',
                      side_effect=errors.AuthenticationRequired):
        result = await flow.async_step_import({
            'host': '0.0.0.0',
        })

    assert result['type'] == 'form'
    assert result['step_id'] == 'link'


async def test_import_with_existing_but_invalid_config(hass):
    """Test importing a host with a config file with invalid username."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    with patch.object(config_flow, '_find_username_from_config',
                      return_value='mock-user'), \
            patch.object(config_flow, 'get_bridge',
                         side_effect=errors.AuthenticationRequired):
        result = await flow.async_step_import({
            'host': '0.0.0.0',
            'path': 'bla.conf'
        })

    assert result['type'] == 'form'
    assert result['step_id'] == 'link'


async def test_import_cannot_connect(hass):
    """Test importing a host that we cannot conncet to."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    with patch.object(config_flow, 'get_bridge',
                      side_effect=errors.CannotConnect):
        result = await flow.async_step_import({
            'host': '0.0.0.0',
        })

    assert result['type'] == 'abort'
    assert result['reason'] == 'cannot_connect'


async def test_creating_entry_removes_entries_for_same_host_or_bridge(hass):
    """Test that we clean up entries for same host and bridge.

    An IP can only hold a single bridge and a single bridge can only be
    accessible via a single IP. So when we create a new entry, we'll remove
    all existing entries that either have same IP or same bridge_id.
    """
    MockConfigEntry(domain='hue', data={
        'host': '0.0.0.0',
        'bridge_id': 'id-1234'
    }).add_to_hass(hass)

    MockConfigEntry(domain='hue', data={
        'host': '1.2.3.4',
        'bridge_id': 'id-1234'
    }).add_to_hass(hass)

    assert len(hass.config_entries.async_entries('hue')) == 2

    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    bridge = Mock()
    bridge.username = 'username-abc'
    bridge.config.bridgeid = 'id-1234'
    bridge.config.name = 'Mock Bridge'
    bridge.host = '0.0.0.0'

    with patch.object(config_flow, 'get_bridge',
                      return_value=mock_coro(bridge)):
        result = await flow.async_step_import({
            'host': '0.0.0.0',
        })

    assert result['type'] == 'create_entry'
    assert result['title'] == 'Mock Bridge'
    assert result['data'] == {
        'host': '0.0.0.0',
        'bridge_id': 'id-1234',
        'username': 'username-abc'
    }
    # We did not process the result of this entry but already removed the old
    # ones. So we should have 0 entries.
    assert len(hass.config_entries.async_entries('hue')) == 0
