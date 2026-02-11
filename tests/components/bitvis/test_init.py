"""Tests for the Bitvis Power Hub integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.bitvis import async_unload_entry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test successful integration setup."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert init_integration.runtime_data is not None


async def test_setup_entry_oserror(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that an OSError during async_start raises ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.bitvis.coordinator.BitvisDataUpdateCoordinator.async_start",
        side_effect=OSError("port in use"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that unloading stops the coordinator and unloads platforms."""
    coordinator = init_integration.runtime_data
    with patch.object(coordinator, "async_stop", new_callable=AsyncMock) as mock_stop:
        assert await hass.config_entries.async_unload(init_integration.entry_id)
        mock_stop.assert_called_once()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_unload_entry_platform_failure(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that async_stop is not called when platform unload fails."""
    coordinator = init_integration.runtime_data
    with (
        patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=False,
        ),
        patch.object(coordinator, "async_stop", new_callable=AsyncMock) as mock_stop,
    ):
        result = await async_unload_entry(hass, init_integration)

    assert result is False
    mock_stop.assert_not_called()
