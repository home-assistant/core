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

    def async_mock(mock):
        async def async_func(*args, **kwargs):
            return mock()

        return async_func

    host = "1.2.3.4"
    hass = Mock()
    entry = Mock()
    entry.data = {"host": host}
    hass.data = {}
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CONFIGS] = {host: {}}
    mock_async_setup = Mock(return_value=True)
    with patch(
        "homeassistant.components.dynalite.__init__.DynaliteBridge.async_setup",
        async_mock(mock_async_setup),
    ):
        assert await async_setup_entry(hass, entry)
    mock_async_setup.assert_called_once()
