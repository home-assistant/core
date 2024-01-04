"""Tests for the TechnoVE integration."""


from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a successful setup entry and unload."""

    init_integration.add_to_hass(hass)
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED
