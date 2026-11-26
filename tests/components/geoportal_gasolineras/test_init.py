"""Tests for setting up Spain fuel prices (Geoportal Gasolineras)."""

from unittest.mock import AsyncMock

from aioprecioscarburantes import PreciosCarburantesConnectionError, StationList
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.geoportal_gasolineras.const import (
    CONF_MUNICIPALITY_ID,
    CONF_PROVINCE_ID,
    CONF_STATION_ID,
    SCAN_INTERVAL,
    SUBENTRY_TYPE_STATION,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.core import HomeAssistant


async def test_setup_and_unload(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test one request per municipality, however many stations it has."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.get_stations_by_municipality.assert_called_once_with("6139")

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup is retried when nothing can be fetched."""
    mock_client.get_stations_by_municipality.side_effect = (
        PreciosCarburantesConnectionError
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_partial_failure(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing municipality does not stop the others and is logged once."""
    antequera_down = True
    stations = mock_client.get_stations_by_municipality.return_value

    async def by_municipality(municipality_id: str) -> StationList:
        if municipality_id == "4469" and antequera_down:
            raise PreciosCarburantesConnectionError
        return stations

    mock_client.get_stations_by_municipality.side_effect = by_municipality
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_STATION,
            title="Gafisur Antequera",
            unique_id="13053",
            data={
                CONF_PROVINCE_ID: "29",
                CONF_MUNICIPALITY_ID: "4469",
                CONF_STATION_ID: "13053",
            },
        ),
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.repsol_la_roda_de_andalucia_diesel_a")
    assert caplog.text.count("Prices of municipality 4469 are unavailable") == 1

    # Still down: not logged again
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert caplog.text.count("Prices of municipality 4469 are unavailable") == 1

    # Back: the recovery is logged
    antequera_down = False
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert "Prices of municipality 4469 are available again" in caplog.text


async def test_reload_on_new_station(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test removing a station reloads the entry and removes its sensors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert hass.states.get("sensor.shell_la_roda_de_andalucia_diesel_a")
    shell = next(
        s for s in mock_config_entry.subentries.values() if s.unique_id == "6440"
    )
    hass.config_entries.async_remove_subentry(mock_config_entry, shell.subentry_id)
    await hass.async_block_till_done()
    assert not hass.states.get("sensor.shell_la_roda_de_andalucia_diesel_a")


async def test_add_station_to_loaded_entry(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test a station added to a loaded, empty entry gets its sensors."""
    entry = MockConfigEntry(domain="geoportal_gasolineras", data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    mock_client.get_stations_by_municipality.assert_not_called()

    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_STATION,
            title="Repsol La Roda de Andalucía",
            unique_id="7370",
            data={
                CONF_PROVINCE_ID: "41",
                CONF_MUNICIPALITY_ID: "6139",
                CONF_STATION_ID: "7370",
            },
        ),
    )
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.repsol_la_roda_de_andalucia_diesel_a").state == "1.825"
    )
