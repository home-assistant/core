"""Tests for the MELCloud device configuration cache."""

from datetime import timedelta
from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_device_configuration_cache_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_devices: AsyncMock,
) -> None:
    """Test that setup passes a five-minute cache interval to MELCloud."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_get_devices.assert_awaited_once()
    assert mock_get_devices.await_args.kwargs["conf_update_interval"] == timedelta(
        minutes=5
    )
