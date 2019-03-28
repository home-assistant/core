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


async def test_setup_entry_already_registered_bridge(hass):
    """Test setup entry doesn't allow more than one instance of deCONZ."""
    hass.data[deconz.DOMAIN] = True
    assert await deconz.async_setup_entry(hass, {}) is False


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
    with patch(
        'pydeconz.DeconzSession.async_load_parameters',
        side_effect=asyncio.TimeoutError
    ), pytest.raises(ConfigEntryNotReady):
        await deconz.async_setup_entry(hass, entry)


async def test_setup_entry_successful(hass):
    """Test setup entry is successful."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'
    })
    entry.add_to_hass(hass)
    mock_registry = Mock()
    with patch.object(deconz, 'DeconzGateway') as mock_gateway, \
        patch('homeassistant.helpers.device_registry.async_get_registry',
              return_value=mock_coro(mock_registry)):
        mock_gateway.return_value.async_setup.return_value = mock_coro(True)
        assert await deconz.async_setup_entry(hass, entry) is True
    assert hass.data[deconz.DOMAIN]


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'
    })
    entry.add_to_hass(hass)
    mock_registry = Mock()
    with patch.object(deconz, 'DeconzGateway') as mock_gateway, \
        patch('homeassistant.helpers.device_registry.async_get_registry',
              return_value=mock_coro(mock_registry)):
        mock_gateway.return_value.async_setup.return_value = mock_coro(True)
        assert await deconz.async_setup_entry(hass, entry) is True

    mock_gateway.return_value.async_reset.return_value = mock_coro(True)
    assert await deconz.async_unload_entry(hass, entry)
    assert deconz.DOMAIN not in hass.data


async def test_service_configure(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'
    })
    entry.add_to_hass(hass)
    mock_registry = Mock()
    with patch.object(deconz, 'DeconzGateway') as mock_gateway, \
        patch('homeassistant.helpers.device_registry.async_get_registry',
              return_value=mock_coro(mock_registry)):
        mock_gateway.return_value.async_setup.return_value = mock_coro(True)
        assert await deconz.async_setup_entry(hass, entry) is True

    hass.data[deconz.DOMAIN].deconz_ids = {
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
        'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'
    })
    entry.add_to_hass(hass)
    mock_registry = Mock()

    with patch.object(deconz, 'DeconzGateway') as mock_gateway, \
        patch('homeassistant.helpers.device_registry.async_get_registry',
              return_value=mock_coro(mock_registry)):
        mock_gateway.return_value.async_setup.return_value = mock_coro(True)
        assert await deconz.async_setup_entry(hass, entry) is True

    with patch.object(hass.data[deconz.DOMAIN].api, 'async_load_parameters',
                      return_value=mock_coro(True)):
        await hass.services.async_call(
            'deconz', 'device_refresh', service_data={})
        await hass.async_block_till_done()

    with patch.object(hass.data[deconz.DOMAIN].api, 'async_load_parameters',
                      return_value=mock_coro(False)):
        await hass.services.async_call(
            'deconz', 'device_refresh', service_data={})
        await hass.async_block_till_done()
