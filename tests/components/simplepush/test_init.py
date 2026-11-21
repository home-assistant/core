"""Test the Simplepush integration setup."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.usefixtures("mock_client")
async def test_load_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading an entry of the current app."""
    await setup_integration(hass, config_entry)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get("notify.simplepush").state == STATE_UNAVAILABLE
