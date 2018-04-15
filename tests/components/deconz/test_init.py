"""Test deCONZ component setup process."""
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.components import deconz


async def test_config_with_host_passed_to_config_entry(hass):
    """Test that configured options for a host are loaded via config entry."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(deconz, 'configured_hosts', return_value=[]), \
            patch.object(deconz, 'load_json', return_value={}):
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {
                deconz.CONF_HOST: '1.2.3.4',
                deconz.CONF_PORT: 80
            }
        }) is True
    # Import flow started
    assert len(mock_config_entries.flow.mock_calls) == 2


async def test_config_file_passed_to_config_entry(hass):
    """Test that configuration file for a host are loaded via config entry."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(deconz, 'configured_hosts', return_value=[]), \
            patch.object(deconz, 'load_json',
                         return_value={'host': '1.2.3.4'}):
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {}
        }) is True
    # Import flow started
    assert len(mock_config_entries.flow.mock_calls) == 2


async def test_config_without_host_not_passed_to_config_entry(hass):
    """Test that a configuration without a host does not initiate an import."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(deconz, 'configured_hosts', return_value=[]), \
            patch.object(deconz, 'load_json', return_value={}):
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {}
        }) is True
    # No flow started
    assert len(mock_config_entries.flow.mock_calls) == 0


async def test_config_already_registered_not_passed_to_config_entry(hass):
    """Test that an already registered host does not initiate an import."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(deconz, 'configured_hosts',
                         return_value=['1.2.3.4']), \
            patch.object(deconz, 'load_json', return_value={}):
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
