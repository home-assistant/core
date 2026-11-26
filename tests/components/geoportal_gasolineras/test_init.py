"""Tests for setting up Spain fuel prices (Geoportal Gasolineras)."""

from unittest.mock import AsyncMock

from aioprecioscarburantes import PreciosCarburantesConnectionError
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.geoportal_gasolineras.const import (
    CONF_MUNICIPALITY_ID,
    CONF_PROVINCE_ID,
    CONF_STATION_ID,
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
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a municipality that cannot be fetched does not stop the others."""

    async def by_municipality(municipality_id: str):  # type: ignore[no-untyped-def]
        if municipality_id == "4469":
            raise PreciosCarburantesConnectionError
        return mock_client.get_stations_by_municipality.return_value

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
