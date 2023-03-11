"""Test InCharge Init Component."""
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import entry, setup_integration


async def test_incharge_setup_unload_entry(hass: HomeAssistant) -> None:
    """Test InCharge Unload."""

    await setup_integration(hass)
    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED
