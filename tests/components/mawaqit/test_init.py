"""Tests for the Mawaqit integration __init__."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    mosque_data = {"name": "Test Mosque", "uuid": "abc"}
    prayer_data = {"calendar": [{}], "timezone": "Europe/Paris"}

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_mosque_by_id",
            new_callable=AsyncMock,
            return_value=mosque_data,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_prayer_times",
            new_callable=AsyncMock,
            return_value=prayer_data,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.mosque_coordinator is not None
    assert mock_config_entry.runtime_data.prayer_time_coordinator is not None


async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful unload of a config entry."""
    mock_config_entry.add_to_hass(hass)

    mosque_data = {"name": "Test Mosque", "uuid": "abc"}
    prayer_data = {"calendar": [{}], "timezone": "Europe/Paris"}

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_mosque_by_id",
            new_callable=AsyncMock,
            return_value=mosque_data,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_prayer_times",
            new_callable=AsyncMock,
            return_value=prayer_data,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
