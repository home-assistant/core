"""Tests for the Moon integration."""

from unittest.mock import patch

from homeassistant.components.moon.const import DOMAIN
from homeassistant.components.moon.helpers import MoonData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    moon_data: MoonData,
) -> None:
    """Test the Moon configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    moon_data.ephemeris.close.assert_called_once()


async def test_setup_retries_when_ephemeris_download_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry is retried when the ephemeris cannot be downloaded."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.moon.load_moon_data", side_effect=OSError):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
