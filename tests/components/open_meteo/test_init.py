"""Tests for the Open-Meteo integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from open_meteo import OpenMeteoConnectionError
import pytest

from homeassistant.components.open_meteo.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ZONE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_open_meteo: AsyncMock,
) -> None:
    """Test the Open-Meteo configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@patch(
    "homeassistant.components.open_meteo.coordinator.OpenMeteo.forecast",
    side_effect=OpenMeteoConnectionError,
)
async def test_config_entry_not_ready(
    mock_forecast: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Open-Meteo configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_forecast.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_zone_removed(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the Open-Meteo configuration entry not ready."""
    mock_config_entry = MockConfigEntry(
        title="My Castle",
        domain=DOMAIN,
        data={CONF_ZONE: "zone.castle"},
        unique_id="zone.castle",
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Zone 'zone.castle' not found" in caplog.text
