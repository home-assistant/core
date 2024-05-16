"""Test Onkyo component setup process."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.onkyo import setup_integration


async def test_load_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_update_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test update options."""

    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        mock_reload.return_value = True
        await setup_integration(hass, config_entry)

        # Force option change
        config_entry.options = {}
        assert hass.config_entries.async_update_entry(
            config_entry, options={"option": "new_value"}
        )
        await hass.async_block_till_done()

        hass.config_entries.async_reload.assert_called_with(config_entry.entry_id)
