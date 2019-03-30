"""Test deCONZ component setup process."""
from unittest.mock import Mock, patch

import asyncio
import pytest
import voluptuous as vol

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component
from homeassistant.components import deconz

from tests.common import mock_coro, MockConfigEntry


CONFIG = {
    "config": {
        "bridgeid": "0123456789ABCDEF",
        "mac": "12:34:56:78:90:ab",
        "modelid": "deCONZ",
        "name": "Phoscon",
        "swversion": "2.05.35"
    }
}


async def setup_entry(hass, entry):
    """Test that setup entry works."""
    with patch.object(deconz.DeconzGateway, 'async_setup',
                      return_value=mock_coro(True)), \
            patch.object(deconz.DeconzGateway, 'async_update_device_registry',
                         return_value=mock_coro(True)):
        assert await deconz.async_setup_entry(hass, entry) is True


async def test_config_with_host_passed_to_config_entry(hass):
    """Test that configured options for a host are loaded via config entry."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(deconz, 'configured_hosts', return_value=[]):
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {
                deconz.CONF_HOST: '1.2.3.4',
                deconz.CONF_PORT: 80
            }
        }) is True
    # Import flow started
    assert len(mock_config_entries.flow.mock_calls) == 2


async def test_config_without_host_not_passed_to_config_entry(hass):
    """Test that a configuration without a host does not initiate an import."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(deconz, 'configured_hosts', return_value=[]):
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {}
        }) is True
    # No flow started
    assert len(mock_config_entries.flow.mock_calls) == 0


async def test_config_already_registered_not_passed_to_config_entry(hass):
    """Test that an already registered host does not initiate an import."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(deconz, 'configured_hosts',
                         return_value=['1.2.3.4']):
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {
                deconz.CONF_HOST: '1.2.3.4',
                deconz.CONF_PORT: 80
            }
        }) is True
    # No flow started
    assert len(mock_config_entries.flow.mock_calls) == 0


async def test_config_discovery(hass):
    """Test that a discovered bridge does not initiate an import."""
    with patch.object(hass, 'config_entries') as mock_config_entries:
        assert await async_setup_component(hass, deconz.DOMAIN, {}) is True
    # No flow started
    assert len(mock_config_entries.flow.mock_calls) == 0


async def test_setup_entry_fails(hass):
    """Test setup entry fails if deCONZ is not available."""
    entry = Mock()
    entry.data = {'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'}
    with patch('pydeconz.DeconzSession.async_load_parameters',
               side_effect=Exception):
        await deconz.async_setup_entry(hass, entry)


async def test_setup_entry_no_available_bridge(hass):
    """Test setup entry fails if deCONZ is not available."""
    entry = Mock()
    entry.data = {'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'}
    with patch('pydeconz.DeconzSession.async_load_parameters',
               side_effect=asyncio.TimeoutError),\
            pytest.raises(ConfigEntryNotReady):
        await deconz.async_setup_entry(hass, entry)


async def test_setup_entry_successful(hass):
    """Test setup entry is successful."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF',
        'bridgeid': '12345'
    })
    entry.add_to_hass(hass)

    await setup_entry(hass, entry)

    assert '12345' in hass.data[deconz.DOMAIN]
    assert hass.data[deconz.DOMAIN]['12345'].master


async def test_setup_entry_multiple_gateways(hass):
    """Test setup entry is successful with multiple gateways."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF',
        'bridgeid': '12345'
    })
    entry.add_to_hass(hass)

    entry2 = MockConfigEntry(domain=deconz.DOMAIN, data={
        'host': '2.3.4.5', 'port': 80, 'api_key': '1234567890ABCDEF',
        'bridgeid': '23456'
    })
    entry2.add_to_hass(hass)

    await setup_entry(hass, entry)
    await setup_entry(hass, entry2)

    assert '12345' in hass.data[deconz.DOMAIN]
    assert hass.data[deconz.DOMAIN]['12345'].master
    assert '23456' in hass.data[deconz.DOMAIN]
    assert not hass.data[deconz.DOMAIN]['23456'].master


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF',
        'bridgeid': '12345'
    })
    entry.add_to_hass(hass)

    await setup_entry(hass, entry)

    with patch.object(deconz.DeconzGateway, 'async_reset',
                      return_value=mock_coro(True)):
        assert await deconz.async_unload_entry(hass, entry)

    assert not hass.data[deconz.DOMAIN]


async def test_unload_entry_multiple_gateways(hass):
    """Test being able to unload an entry and master gateway gets moved."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF',
        'bridgeid': '12345'
    })
    entry.add_to_hass(hass)

    entry2 = MockConfigEntry(domain=deconz.DOMAIN, data={
        'host': '2.3.4.5', 'port': 80, 'api_key': '1234567890ABCDEF',
        'bridgeid': '23456'
    })
    entry2.add_to_hass(hass)

    await setup_entry(hass, entry)
    await setup_entry(hass, entry2)

    with patch.object(deconz.DeconzGateway, 'async_reset',
                      return_value=mock_coro(True)):
        assert await deconz.async_unload_entry(hass, entry)

    assert '23456' in hass.data[deconz.DOMAIN]
    assert hass.data[deconz.DOMAIN]['23456'].master


async def test_service_configure(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF',
        'bridgeid': '12345'
    })
    entry.add_to_hass(hass)

    await setup_entry(hass, entry)

    hass.data[deconz.DOMAIN]['12345'].deconz_ids = {
        'light.test': '/light/1'
    }
    data = {'on': True, 'attr1': 10, 'attr2': 20}

    # only field
    with patch('pydeconz.DeconzSession.async_put_state',
               return_value=mock_coro(True)):
        await hass.services.async_call('deconz', 'configure', service_data={
            'field': '/light/42', 'data': data
        })
        await hass.async_block_till_done()

    # only entity
    with patch('pydeconz.DeconzSession.async_put_state',
               return_value=mock_coro(True)):
        await hass.services.async_call('deconz', 'configure', service_data={
            'entity': 'light.test', 'data': data
        })
        await hass.async_block_till_done()

    # entity + field
    with patch('pydeconz.DeconzSession.async_put_state',
               return_value=mock_coro(True)):
        await hass.services.async_call('deconz', 'configure', service_data={
            'entity': 'light.test', 'field': '/state', 'data': data})
        await hass.async_block_till_done()

    # non-existing entity (or not from deCONZ)
    with patch('pydeconz.DeconzSession.async_put_state',
               return_value=mock_coro(True)):
        await hass.services.async_call('deconz', 'configure', service_data={
            'entity': 'light.nonexisting', 'field': '/state', 'data': data})
        await hass.async_block_till_done()

    # field does not start with /
    with pytest.raises(vol.Invalid):
        with patch('pydeconz.DeconzSession.async_put_state',
                   return_value=mock_coro(True)):
            await hass.services.async_call(
                'deconz', 'configure', service_data={
                    'entity': 'light.test', 'field': 'state', 'data': data})
            await hass.async_block_till_done()


async def test_service_refresh_devices(hass):
    """Test that service can refresh devices."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF',
        'bridgeid': '12345'
    })
    entry.add_to_hass(hass)

    await setup_entry(hass, entry)

    with patch('pydeconz.DeconzSession.async_load_parameters',
               return_value=mock_coro(True)):
        await hass.services.async_call(
            'deconz', 'device_refresh', service_data={})
        await hass.async_block_till_done()

    with patch('pydeconz.DeconzSession.async_load_parameters',
               return_value=mock_coro(False)):
        await hass.services.async_call(
            'deconz', 'device_refresh', service_data={})
        await hass.async_block_till_done()
