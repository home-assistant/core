"""Test Dynalite __init__."""
from unittest.mock import Mock, patch, call

from homeassistant.components.dynalite import DOMAIN, DATA_CONFIGS
from homeassistant.components.dynalite.__init__ import async_setup, async_setup_entry


async def test_async_setup():
    """Test a successful setup."""
    new_host = "1.2.3.4"
    old_host = "5.6.7.8"
    hass = Mock()
    hass.data = {}
    config = {DOMAIN: {"bridges": [{"host": old_host}, {"host": new_host}]}}
    mock_conf_host = Mock(return_value=[old_host])
    with patch(
        "homeassistant.components.dynalite.__init__.configured_hosts", mock_conf_host
    ):
        await async_setup(hass, config)
        mock_conf_host.assert_called_once()
        assert mock_conf_host.mock_calls[0] == call(hass)
        assert hass.data[DOMAIN][DATA_CONFIGS] == {
            new_host: {"host": new_host},
            old_host: {"host": old_host},
        }
        hass.async_create_task.assert_called_once()


async def test_async_setup_entry():
    """Test setup of an entry."""

    async def temp_async_setup():
        return True

    host = "1.2.3.4"
    hass = Mock()
    entry = Mock()
    entry.data = {"host": host}
    hass.data = {}
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CONFIGS] = {host: {}}
    mock_instance = Mock()
    mock_instance.async_setup = temp_async_setup
    mock_bridge = Mock(return_value=mock_instance)
    with patch(
        "homeassistant.components.dynalite.__init__.DynaliteBridge", mock_bridge
    ):
        await async_setup_entry(hass, entry)
    assert hass.data[DOMAIN][host] is mock_instance
