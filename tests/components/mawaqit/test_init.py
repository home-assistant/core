"""Tests for the Mawaqit integration __init__."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
) -> None:
    """Test successful setup of a config entry."""
    await setup_mawaqit_integration()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.mosque_coordinator is not None
    assert mock_config_entry.runtime_data.prayer_time_coordinator is not None


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
) -> None:
    """Test successful unload of a config entry."""
    await setup_mawaqit_integration()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
