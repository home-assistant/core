"""Tests for the easyEnergy integration."""

from datetime import date
from unittest.mock import MagicMock, patch

from easyenergy import EasyEnergyConnectionError, EasyEnergyNoDataError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_easyenergy: MagicMock
) -> None:
    """Test the easyEnergy configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.freeze_time("2026-04-19 14:00:00+00:00")
async def test_load_config_entry_without_tomorrow_energy_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_easyenergy: MagicMock
) -> None:
    """Test the entry loads when tomorrow's energy data is not available yet."""
    mock_easyenergy.energy_prices.side_effect = [
        mock_easyenergy.energy_prices.return_value,
        EasyEnergyNoDataError,
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_easyenergy.energy_prices.call_count == 2
    assert mock_config_entry.runtime_data.data.energy_tomorrow is None


@patch(
    "homeassistant.components.easyenergy.coordinator.EasyEnergy._request",
    side_effect=EasyEnergyConnectionError,
)
async def test_config_flow_entry_not_ready(
    mock_request: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the easyEnergy configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.freeze_time("2026-04-19 14:00:00+00:00")
async def test_no_energy_tomorrow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_easyenergy: MagicMock
) -> None:
    """Test the coordinator handles missing tomorrow energy prices."""
    mock_easyenergy.energy_prices.side_effect = [
        mock_easyenergy.energy_prices.return_value,
        EasyEnergyNoDataError,
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.data.energy_tomorrow is None
    assert mock_easyenergy.energy_prices.call_count == 2
    mock_easyenergy.energy_prices.assert_any_call(
        start_date=date(2026, 4, 19), end_date=date(2026, 4, 19)
    )
    mock_easyenergy.energy_prices.assert_any_call(
        start_date=date(2026, 4, 20), end_date=date(2026, 4, 20)
    )
