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


async def test_unload_entry(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry is unloaded successfully."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


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


async def test_setup_entry_connections_api_unavailable(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry is retried when the coordinator cannot fetch data."""
    mock_nmbs_client.get_connections.return_value = None
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_unknown_station(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
) -> None:
    """Test setup fails when a configured station no longer exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Train from nowhere to Brussel-Zuid/Bruxelles-Midi",
        data={
            CONF_STATION_FROM: "BE.NMBS.999999999",
            CONF_STATION_TO: "BE.NMBS.008814001",
        },
        unique_id="BE.NMBS.999999999_BE.NMBS.008814001",
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
