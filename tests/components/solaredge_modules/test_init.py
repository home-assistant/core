"""Tests for the SolarEdge Modules integration."""

from unittest.mock import AsyncMock

import aiohttp

from homeassistant.components.recorder import Recorder
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_unload_entry(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test successful setup and unload of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_solar_edge_web.async_get_equipment.assert_awaited_once()
    mock_solar_edge_web.async_get_energy_data.assert_awaited_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_not_ready(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test for setup failure."""
    mock_solar_edge_web.async_get_equipment.side_effect = aiohttp.ClientError()

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
