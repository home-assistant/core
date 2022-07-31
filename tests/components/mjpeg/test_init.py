"""Tests for the MJPEG IP Camera integration."""
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.mjpeg.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mjpeg_requests: MagicMock,
) -> None:
    """Test the MJPEG IP Camera configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_reload_config_entry(
    hass: HomeAssistant,
    mock_reload_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the MJPEG IP Camera configuration entry is reloaded on change."""
    assert len(mock_reload_entry.mock_calls) == 0
    hass.config_entries.async_update_entry(
        init_integration, options={"something": "else"}
    )
    assert len(mock_reload_entry.mock_calls) == 1
