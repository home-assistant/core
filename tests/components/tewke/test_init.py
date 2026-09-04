"""Test the Tewke integration."""

from unittest.mock import AsyncMock

from pytewke.error import PyTewkeDiscoveryError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test setup and unload of the Tewke integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_tap.discover.call_count == 1

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]
    assert mock_tap.close.call_count == 1


async def test_setup_discovery_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test setup handles discovery error."""
    mock_tap.discover.side_effect = PyTewkeDiscoveryError
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_tap.close.call_count == 1


async def test_setup_missing_wall_dock_id(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test setup handles missing wall_dock_id."""
    mock_tap.wall_dock_id = None
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_tap.close.call_count == 1


async def test_async_reload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test reload of the Tewke integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_tap.discover.call_count == 1

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_tap.discover.call_count == 2


async def test_update_listener(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test update listener."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_tap.discover.call_count == 1

    hass.config_entries.async_update_entry(mock_config_entry, title="New Title")
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    # Verify the reload happened
    assert mock_tap.discover.call_count == 2
