"""Tests for the Spain fuel prices (Geoportal Gasolineras) config flow."""

from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock

from aioprecioscarburantes import PreciosCarburantesConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.geoportal_gasolineras.const import (
    CONF_MUNICIPALITY_ID,
    CONF_PROVINCE_ID,
    CONF_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_STATION,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_flow(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test creating the entry, with a connection error and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    mock_client.get_provinces.side_effect = PreciosCarburantesConnectionError
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}

    mock_client.get_provinces.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Spain fuel prices"
    assert result["data"] == {}


async def test_single_instance(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test only one entry can be created."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.fixture
def empty_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return an entry without stations."""
    entry = MockConfigEntry(domain=DOMAIN, title="Spain fuel prices", data={})
    entry.add_to_hass(hass)
    return entry


async def _start(hass: HomeAssistant, entry: MockConfigEntry) -> FlowResult:
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STATION), context={"source": SOURCE_USER}
    )


async def _configure(
    hass: HomeAssistant, result: FlowResult, data: dict[str, Any]
) -> FlowResult:
    return await hass.config_entries.subentries.async_configure(result["flow_id"], data)


async def test_add_station(
    hass: HomeAssistant, mock_client: AsyncMock, empty_entry: MockConfigEntry
) -> None:
    """Test adding a station from the list."""
    result = await _start(hass, empty_entry)
    assert result["step_id"] == "user"
    result = await _configure(hass, result, {CONF_PROVINCE_ID: "41"})
    assert result["step_id"] == "municipality"
    mock_client.get_municipalities.assert_called_with("41")
    result = await _configure(hass, result, {CONF_MUNICIPALITY_ID: "6139"})
    assert result["step_id"] == "station"
    result = await _configure(hass, result, {CONF_STATION_ID: "7370"})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    subentry = next(iter(empty_entry.subentries.values()))
    assert subentry.title == "Repsol La Roda de Andalucía"
    assert subentry.unique_id == "7370"
    assert subentry.data == {
        CONF_PROVINCE_ID: "41",
        CONF_MUNICIPALITY_ID: "6139",
        CONF_STATION_ID: "7370",
    }


async def test_added_stations_not_offered(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the stations already added are not offered, and none left aborts."""
    mock_config_entry.add_to_hass(hass)
    result = await _start(hass, mock_config_entry)
    result = await _configure(hass, result, {CONF_PROVINCE_ID: "41"})
    result = await _configure(hass, result, {CONF_MUNICIPALITY_ID: "6139"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_stations"


@pytest.mark.parametrize(
    ("method", "steps"),
    [
        ("get_provinces", []),
        ("get_municipalities", [{CONF_PROVINCE_ID: "41"}]),
        (
            "get_stations_by_municipality",
            [{CONF_PROVINCE_ID: "41"}, {CONF_MUNICIPALITY_ID: "6139"}],
        ),
    ],
)
async def test_abort_cannot_connect(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    empty_entry: MockConfigEntry,
    method: str,
    steps: list[dict[str, Any]],
) -> None:
    """Test adding a station aborts when a list cannot be fetched."""
    getattr(mock_client, method).side_effect = PreciosCarburantesConnectionError
    result = await _start(hass, empty_entry)
    for step in steps:
        assert result["type"] is FlowResultType.FORM
        result = await _configure(hass, result, step)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    getattr(mock_client, method).assert_called_once()


async def test_same_label_gets_code(
    hass: HomeAssistant, mock_client: AsyncMock, empty_entry: MockConfigEntry
) -> None:
    """Test stations with the same brand and address show their code."""
    stations = mock_client.get_stations_by_municipality.return_value
    shell = stations.stations[1]
    mock_client.get_stations_by_municipality.return_value = replace(
        stations, stations=[*stations.stations, replace(shell, id="1")]
    )
    result = await _start(hass, empty_entry)
    result = await _configure(hass, result, {CONF_PROVINCE_ID: "41"})
    result = await _configure(hass, result, {CONF_MUNICIPALITY_ID: "6139"})
    labels = sorted(
        option["label"]
        for option in result["data_schema"].schema[CONF_STATION_ID].config["options"]
    )
    assert labels == [
        "Repsol – Carretera Malaga, Granada, Sevilla Km. 124,90",
        "Shell – Autovia Autovia A-92 Km. 123 (#1)",
        "Shell – Autovia Autovia A-92 Km. 123 (#6440)",
    ]


async def test_added_meanwhile(
    hass: HomeAssistant, mock_client: AsyncMock, empty_entry: MockConfigEntry
) -> None:
    """Test a station added in another flow meanwhile is not added twice."""
    flows = []
    for _ in range(2):
        result = await _start(hass, empty_entry)
        result = await _configure(hass, result, {CONF_PROVINCE_ID: "41"})
        flows.append(await _configure(hass, result, {CONF_MUNICIPALITY_ID: "6139"}))
    result = await _configure(hass, flows[0], {CONF_STATION_ID: "7370"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    result = await _configure(hass, flows[1], {CONF_STATION_ID: "7370"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(empty_entry.subentries) == 1


@pytest.mark.parametrize(
    ("brand", "municipality", "title"),
    [
        ("REPSOL", "Roda de Andalucía (La)", "Repsol La Roda de Andalucía"),
        ("BP", "Palmas de Gran Canaria (Las)", "BP Las Palmas de Gran Canaria"),
        ("CEPSA", "Hospitalet de Llobregat (L')", "Cepsa L'Hospitalet de Llobregat"),
        ("PETROPRIX", "Sevilla", "Petroprix Sevilla"),
    ],
)
async def test_station_title(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    empty_entry: MockConfigEntry,
    brand: str,
    municipality: str,
    title: str,
) -> None:
    """Test the readable station name: brand, then the town with its article."""
    stations = mock_client.get_stations_by_municipality.return_value
    mock_client.get_stations_by_municipality.return_value = replace(
        stations,
        stations=[
            replace(stations.stations[0], brand=brand, municipality=municipality)
        ],
    )
    result = await _start(hass, empty_entry)
    result = await _configure(hass, result, {CONF_PROVINCE_ID: "41"})
    result = await _configure(hass, result, {CONF_MUNICIPALITY_ID: "6139"})
    result = await _configure(hass, result, {CONF_STATION_ID: "7370"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert next(iter(empty_entry.subentries.values())).title == title
