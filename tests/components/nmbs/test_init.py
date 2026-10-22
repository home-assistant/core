"""Test the NMBS integration setup."""

from unittest.mock import AsyncMock

from mashumaro.exceptions import MissingField
from pyrail import ApiUnavailableError
from pyrail.models import StationsApiResponse
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.nmbs.const import (
    CONF_STATION_FROM,
    CONF_STATION_TO,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import STATION_TO


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


@pytest.mark.parametrize(
    "stations_side_effect",
    [
        pytest.param([None], id="no_response"),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(ApiUnavailableError("API unavailable"), id="api_unavailable"),
        pytest.param(ValueError("Unexpected response schema"), id="decoding_error"),
        pytest.param(MissingField("name", "str", "StationDetails"), id="missing_field"),
    ],
)
async def test_setup_entry_station_list_unavailable(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    stations_side_effect: list[None] | Exception | type[Exception],
) -> None:
    """Test the entry is retried when the station list cannot be fetched."""
    mock_nmbs_client.get_stations.side_effect = stations_side_effect
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_connections_api_unavailable(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry loads when the connections API is unavailable."""
    mock_nmbs_client.get_connections.return_value = None
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


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
            CONF_STATION_TO: STATION_TO,
        },
        unique_id=f"BE.NMBS.999999999_{STATION_TO}",
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_finds_new_station_after_reload(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fetches a fresh station list each time it runs."""
    stations = mock_nmbs_client.get_stations.return_value
    mock_nmbs_client.get_stations.return_value = StationsApiResponse(
        version=stations.version,
        timestamp=stations.timestamp,
        stations=[station for station in stations.stations if station.id != STATION_TO],
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    mock_nmbs_client.get_stations.return_value = stations
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
