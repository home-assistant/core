"""Tests for the Rhasspy integration."""
from spencerassistant.components.rhasspy.const import DOMAIN
from spencerassistant.config_entries import ConfigEntryState
from spencerassistant.core import spencerAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(hass: spencerAssistant) -> None:
    """Test the Rhasspy configuration entry loading/unloading."""
    mock_config_entry = MockConfigEntry(
        title="Rhasspy",
        domain=DOMAIN,
        data={},
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
