"""Test emulated_roku component setup process."""
from unittest.mock import Mock, patch

from homeassistant.setup import async_setup_component
from homeassistant.components import emulated_roku

from tests.common import mock_coro

CONFIG = {
    "config": {
        "name": "Emulated Roku Test",
        "listen_port": "8060"
    }
}


async def test_config_required_fields(hass):
    """Test that configuration is successful with required fields."""
    with patch.object(emulated_roku, 'configured_servers', return_value=[]), \
            patch('emulated_roku.make_roku_api',
                  return_value=mock_coro(((None, None), None))):
        assert await async_setup_component(hass, emulated_roku.DOMAIN, {
            emulated_roku.DOMAIN: {
                emulated_roku.CONF_SERVERS: [{
                    emulated_roku.CONF_NAME: 'Emulated Roku Test',
                    emulated_roku.CONF_LISTEN_PORT: 8060
                }]
            }
        }) is True


async def test_config_already_registered_not_configured(hass):
    """Test that an already registered name causes the entry to be ignored."""
    with patch.object(emulated_roku, "create_emulated_roku",
                      return_value=mock_coro(True)) as mock_create, \
            patch.object(emulated_roku, 'configured_servers',
                         return_value=['emulated_roku_test']):
        assert await async_setup_component(hass, emulated_roku.DOMAIN, {
            emulated_roku.DOMAIN: {
                emulated_roku.CONF_SERVERS: [{
                    emulated_roku.CONF_NAME: 'Emulated Roku Test',
                    emulated_roku.CONF_LISTEN_PORT: 8060
                }]
            }
        }) is True

    assert len(mock_create.mock_calls) == 0


async def test_setup_entry_successful(hass):
    """Test setup entry is successful."""
    entry = Mock()
    entry.data = {'name': 'Emulated Roku Test', 'port': 8060}
    with patch('emulated_roku.make_roku_api',
               return_value=mock_coro(((None, None), None))):
        assert await emulated_roku.async_setup_entry(hass, entry) is True
    assert hass.data[emulated_roku.DOMAIN]


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = Mock()
    entry.data = {'name': 'Emulated Roku Test', 'listen_port': 8060}
    with patch('emulated_roku.make_roku_api',
               return_value=mock_coro(((None, None), None))):
        assert await emulated_roku.async_setup_entry(hass, entry) is True

    assert emulated_roku.DOMAIN in hass.data

    assert await emulated_roku.async_unload_entry(hass, entry)
    assert len(hass.data[emulated_roku.DOMAIN]) == 0
