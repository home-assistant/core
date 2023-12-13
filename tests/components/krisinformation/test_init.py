"""Tests for init."""

import pytest

from homeassistant.components.krisinformation.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_load_unload_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the krisinformation entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
