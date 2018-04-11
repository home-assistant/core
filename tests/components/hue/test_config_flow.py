"""Tests for Philips Hue config flow."""
import asyncio
from unittest.mock import patch

import aiohue
import pytest
import voluptuous as vol

from homeassistant.components import hue

from tests.common import MockConfigEntry, mock_coro


async def test_flow_works(hass, aioclient_mock):
    """Test config flow ."""
    aioclient_mock.get(hue.API_NUPNP, json=[
        {'internalipaddress': '1.2.3.4', 'id': 'bla'}
    ])

    flow = hue.HueFlowHandler()
    flow.hass = hass
    await flow.async_step_init()

    with patch('aiohue.Bridge') as mock_bridge:
        def mock_constructor(host, websession):
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
    aioclient_mock.get(hue.API_NUPNP, json=[])
    flow = hue.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'abort'


async def test_flow_all_discovered_bridges_exist(hass, aioclient_mock):
    """Test config flow discovers only already configured bridges."""
    aioclient_mock.get(hue.API_NUPNP, json=[
        {'internalipaddress': '1.2.3.4', 'id': 'bla'}
    ])
    MockConfigEntry(domain='hue', data={
        'host': '1.2.3.4'
    }).add_to_hass(hass)
    flow = hue.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'abort'


async def test_flow_one_bridge_discovered(hass, aioclient_mock):
    """Test config flow discovers one bridge."""
    aioclient_mock.get(hue.API_NUPNP, json=[
        {'internalipaddress': '1.2.3.4', 'id': 'bla'}
    ])
    flow = hue.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'form'
    assert result['step_id'] == 'link'


async def test_flow_two_bridges_discovered(hass, aioclient_mock):
    """Test config flow discovers two bridges."""
    aioclient_mock.get(hue.API_NUPNP, json=[
        {'internalipaddress': '1.2.3.4', 'id': 'bla'},
        {'internalipaddress': '5.6.7.8', 'id': 'beer'}
    ])
    flow = hue.HueFlowHandler()
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
    aioclient_mock.get(hue.API_NUPNP, json=[
        {'internalipaddress': '1.2.3.4', 'id': 'bla'},
        {'internalipaddress': '5.6.7.8', 'id': 'beer'}
    ])
    MockConfigEntry(domain='hue', data={
        'host': '1.2.3.4'
    }).add_to_hass(hass)
    flow = hue.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result['type'] == 'form'
    assert result['step_id'] == 'link'
    assert flow.host == '5.6.7.8'


async def test_flow_timeout_discovery(hass):
    """Test config flow ."""
    flow = hue.HueFlowHandler()
    flow.hass = hass

    with patch('aiohue.discovery.discover_nupnp',
               side_effect=asyncio.TimeoutError):
        result = await flow.async_step_init()

    assert result['type'] == 'abort'


async def test_flow_link_timeout(hass):
    """Test config flow ."""
    flow = hue.HueFlowHandler()
    flow.hass = hass

    with patch('aiohue.Bridge.create_user',
               side_effect=asyncio.TimeoutError):
        result = await flow.async_step_link({})

    assert result['type'] == 'form'
    assert result['step_id'] == 'link'
    assert result['errors'] == {
        'base': 'register_failed'
    }


async def test_flow_link_button_not_pressed(hass):
    """Test config flow ."""
    flow = hue.HueFlowHandler()
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
    flow = hue.HueFlowHandler()
    flow.hass = hass

    with patch('aiohue.Bridge.create_user',
               side_effect=aiohue.RequestError):
        result = await flow.async_step_link({})

    assert result['type'] == 'form'
    assert result['step_id'] == 'link'
    assert result['errors'] == {
        'base': 'register_failed'
    }
