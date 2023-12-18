"""Integration tests for the Tailwind integration."""
from unittest.mock import MagicMock

from gotailwind import TailwindConnectionError

from homeassistant.components.tailwind.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailwind: MagicMock,
) -> None:
    """Test the Tailwind configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_tailwind.status.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailwind: MagicMock,
) -> None:
    """Test the Tailwind configuration entry not ready."""
    mock_tailwind.status.side_effect = TailwindConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_tailwind.status.mock_calls) == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
