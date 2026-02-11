"""Tests for the Bitvis Power Hub integration."""

from unittest.mock import MagicMock

from homeassistant.components.bitvis.const import DEFAULT_PORT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test successful integration setup."""
    assert init_integration.state is ConfigEntryState.LOADED
    patch_shared_listener.start.assert_awaited_once_with(DEFAULT_PORT)
    patch_shared_listener.register.assert_called_once()


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that unloading stops the coordinator and unloads platforms."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED
