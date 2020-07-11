"""Test SMHI component setup process."""
from homeassistant.components import smhi

from .common import AsyncMock

from tests.async_mock import Mock

TEST_CONFIG = {
    "config": {
        "name": "0123456789ABCDEF",
        "longitude": "62.0022",
        "latitude": "17.0022",
    }
}


async def test_setup_always_return_true() -> None:
    """Test async_setup always returns True."""
    hass = Mock()
    # Returns true with empty config
    assert await smhi.async_setup(hass, {}) is True

    # Returns true with a config provided
    assert await smhi.async_setup(hass, TEST_CONFIG) is True


async def test_forward_async_setup_entry() -> None:
    """Test that it will forward setup entry."""
    hass = Mock()

    assert await smhi.async_setup_entry(hass, {}) is True
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 1


async def test_forward_async_unload_entry() -> None:
    """Test that it will forward unload entry."""
    hass = AsyncMock()
    assert await smhi.async_unload_entry(hass, {}) is True
    assert len(hass.config_entries.async_forward_entry_unload.mock_calls) == 1
