"""Test __init__.py for School Holiday integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_school_holiday_data
) -> None:
    """Test setting up a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.school_holiday.coordinator.SchoolHolidayCoordinator._async_update_data",
        new_callable=AsyncMock,
        return_value=mock_school_holiday_data,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

        assert result is True
        assert mock_config_entry.state == ConfigEntryState.LOADED


@pytest.mark.asyncio
async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_school_holiday_data
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.school_holiday.coordinator.SchoolHolidayCoordinator._async_update_data",
        new_callable=AsyncMock,
        return_value=mock_school_holiday_data,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)

        assert result is True
        assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
