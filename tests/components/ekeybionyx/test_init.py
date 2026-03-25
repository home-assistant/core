"""Module contains tests for the ekeybionyx component's initialization.

Functions:
    test_async_setup_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
        Test a successful setup entry and unload of entry.
"""

from homeassistant.components.ekeybionyx.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test a successful setup entry and unload of entry."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
