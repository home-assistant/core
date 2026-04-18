"""Test Green Planet Energy setup."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test setting up config entry."""
    assert init_integration.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test unloading config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    result = await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert result
    assert init_integration.state is ConfigEntryState.NOT_LOADED
