"""Test Duosida EV integration setup and unload."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant.components.duosida_ev import async_setup_entry, async_unload_entry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_platforms_are_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_charger: Any,
) -> None:
    """Test that all platforms are loaded."""
    # Note: mock_config_entry fixture already adds entry to hass

    with (
        patch(
            "homeassistant.components.duosida_ev.DuosidaDataUpdateCoordinator.async_load_stored_settings",
            return_value=None,
        ),
        patch(
            "homeassistant.components.duosida_ev.DuosidaDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=None,
        ) as mock_forward,
    ):
        assert await async_setup_entry(hass, mock_config_entry)
        await hass.async_block_till_done()

        # Verify platforms were loaded
        assert mock_forward.called
        # Should load sensor platform
        loaded_platforms = mock_forward.call_args[0][1]
        assert Platform.SENSOR in loaded_platforms


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_charger: Any,
) -> None:
    """Test unloading the config entry."""
    with (
        patch(
            "homeassistant.components.duosida_ev.coordinator.Store.async_load",
            return_value=None,
        ),
        patch(
            "homeassistant.components.duosida_ev.coordinator.Store.async_save",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert await async_unload_entry(hass, mock_config_entry)
        await hass.async_block_till_done()
