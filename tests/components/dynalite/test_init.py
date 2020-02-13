"""Test Dynalite __init__."""
from unittest.mock import Mock, call, patch

from homeassistant.components.dynalite import DATA_CONFIGS, DOMAIN
from homeassistant.components.dynalite.__init__ import (
    async_setup,
    async_setup_entry,
    async_unload_entry,
)

from tests.common import mock_coro


async def test_empty_config():
    """Test with an empty config."""
    hass = Mock()
    hass.data = {}
    config = {}
    assert await async_setup(hass, config)
    assert hass.data[DOMAIN] == {DATA_CONFIGS: {}}


async def test_async_setup():
    """Test a successful setup."""
    host = "1.2.3.4"
    hass = Mock()
    hass.data = {}
    config = {DOMAIN: {"bridges": [{"host": host}]}}
    await async_setup(hass, config)
    assert hass.data[DOMAIN][DATA_CONFIGS] == {
        host: {"host": host},
    }
    hass.async_create_task.assert_called_once()


async def test_async_setup_entry():
    """Test setup of an entry."""

    def async_mock(mock):
        """Return the return value of a mock from async."""

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


async def test_failed_setup_entry():
    """Test when bridge setup fails."""

    def async_mock(mock):
        """Return the return value of a mock from async."""

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
    mock_async_setup = Mock(return_value=False)
    with patch(
        "homeassistant.components.dynalite.__init__.DynaliteBridge.async_setup",
        async_mock(mock_async_setup),
    ):
        assert not await async_setup_entry(hass, entry)
    mock_async_setup.assert_called_once()


async def test_async_unload_entry():
    """Test unloading of an entry."""
    hass = Mock()
    mock_bridge = Mock()
    mock_bridge.async_reset.return_value = mock_coro(True)
    entry = Mock()
    hass.data = {}
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = mock_bridge
    await async_unload_entry(hass, entry)
    mock_bridge.async_reset.assert_called_once()
    assert mock_bridge.mock_calls[0] == call.async_reset()
