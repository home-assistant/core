"""Tests for the Gatus integration setup and unload lifecycle."""

from unittest.mock import patch

from homeassistant.components.gatus.coordinator import GatusDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


async def test_setup_and_unload_entry(hass: HomeAssistant, setup_integration) -> None:
    """Test standard successful setup and unload cycle of the integration."""
    mock_data = [{"key": "endpoint_1", "is_up": True}]

    config_entry = await setup_integration(mock_data)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None
    assert isinstance(config_entry.runtime_data, GatusDataUpdateCoordinator)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_failing_first_refresh(
    hass: HomeAssistant,
    setup_integration,
) -> None:
    """Test setup failure when the initial coordinator data fetch fails."""
    with patch(
        "homeassistant.components.gatus.coordinator.GatusDataUpdateCoordinator.async_config_entry_first_refresh",
        side_effect=ConfigEntryNotReady("Connection timed out"),
    ):
        config_entry = await setup_integration([])

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
