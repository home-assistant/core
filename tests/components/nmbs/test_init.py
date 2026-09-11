"""Test the NMBS integration setup."""

import asyncio
from unittest.mock import AsyncMock

from pyrail.models import StationsApiResponse
import pytest

from homeassistant.components.nmbs.const import (
    CONF_STATION_FROM,
    CONF_STATION_TO,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_load_json_object_fixture


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


@pytest.mark.parametrize(
    ("station_from", "station_to", "missing_station"),
    [
        pytest.param(
            "BE.NMBS.000000000",
            "BE.NMBS.008814001",
            "BE.NMBS.000000000",
            id="departure",
        ),
        pytest.param(
            "BE.NMBS.008812005", "BE.NMBS.000000000", "BE.NMBS.000000000", id="arrival"
        ),
    ],
)
@pytest.mark.usefixtures("mock_nmbs_client")
async def test_setup_entry_unknown_station(
    hass: HomeAssistant,
    station_from: str,
    station_to: str,
    missing_station: str,
) -> None:
    """Test the entry errors when a configured station is not in the station list."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Train from an unknown station",
        data={CONF_STATION_FROM: station_from, CONF_STATION_TO: station_to},
        unique_id=f"{station_from}_{station_to}",
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "station_not_found"
    assert entry.error_reason_translation_placeholders == {"station": missing_station}


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
    # The two entries use the same stations swapped, so resolving both against
    # the same shared list yields the very same station objects.
    assert (
        second_entry.runtime_data.station_from
        is mock_config_entry.runtime_data.station_to
    )
    mock_nmbs_client.get_stations.assert_called_once()


async def test_concurrent_setup_shares_station_fetch(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that entries set up concurrently share one in-flight station fetch."""
    stations_response = mock_nmbs_client.get_stations.return_value
    release_fetch = asyncio.Event()

    async def _blocked_get_stations() -> StationsApiResponse:
        await release_fetch.wait()
        return stations_response

    mock_nmbs_client.get_stations.side_effect = _blocked_get_stations

    mock_config_entry.add_to_hass(hass)
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

    setup_task = hass.async_create_task(async_setup_component(hass, DOMAIN, {}))
    # Release the fetch only after both entry setups are underway, so the
    # second entry sees the first entry's fetch in flight rather than a
    # completed task.
    async with asyncio.timeout(10):
        while (
            mock_config_entry.state is not ConfigEntryState.SETUP_IN_PROGRESS
            or second_entry.state is not ConfigEntryState.SETUP_IN_PROGRESS
        ):
            await asyncio.sleep(0)
    release_fetch.set()

    assert await setup_task
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert second_entry.state is ConfigEntryState.LOADED
    assert (
        second_entry.runtime_data.station_from
        is mock_config_entry.runtime_data.station_to
    )
    mock_nmbs_client.get_stations.assert_called_once()


async def test_setup_retry_after_failed_fetch(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a failed station fetch is not reused on a setup retry."""
    mock_nmbs_client.get_stations.return_value = None
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_nmbs_client.get_stations.return_value = StationsApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "stations.json", DOMAIN)
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
