"""Test the IamMeter component."""
from homeassistant.components import iammeter

from tests.async_mock import Mock


async def test_setup(hass):
    """Test setup function."""
    config = {}
    assert await iammeter.async_setup(hass, config) is True


async def test_async_setup_entry(hass):
    """Test that it will forward setup entry."""
    hass = Mock()
    assert await iammeter.async_setup_entry(hass, {}) is True
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 1
