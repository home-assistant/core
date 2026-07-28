"""Test the NMBS integration setup."""

from unittest.mock import AsyncMock

from homeassistant.components.nmbs.const import (
    CONF_STATION_FROM,
    CONF_STATION_TO,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry is set up successfully."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_api_unavailable(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry is retried when the station list cannot be fetched."""
    mock_nmbs_client.get_stations.return_value = None
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_second_entry_reuses_station_list(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a second entry reuses the station list of a loaded entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    second_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Train from Brussel-Zuid/Bruxelles-Midi to Brussel-Noord/Bruxelles-Nord",
        data={
            CONF_STATION_FROM: "BE.NMBS.008814001",
            CONF_STATION_TO: "BE.NMBS.008812005",
        },
        unique_id="BE.NMBS.008814001_BE.NMBS.008812005",
    )
    second_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    assert second_entry.state is ConfigEntryState.LOADED
    assert second_entry.runtime_data is mock_config_entry.runtime_data
    mock_nmbs_client.get_stations.assert_called_once()
