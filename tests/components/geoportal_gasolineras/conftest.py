"""Fixtures for the Spain fuel prices (Geoportal Gasolineras) tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aioprecioscarburantes import Municipality, Province, StationList
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

from homeassistant.components.geoportal_gasolineras.const import (
    CONF_MUNICIPALITY_ID,
    CONF_PROVINCE_ID,
    CONF_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_STATION,
)
from homeassistant.config_entries import ConfigSubentryData


def _station(title: str, station_id: str) -> ConfigSubentryData:
    return ConfigSubentryData(
        subentry_type=SUBENTRY_TYPE_STATION,
        title=title,
        unique_id=station_id,
        data={
            CONF_PROVINCE_ID: "41",
            CONF_MUNICIPALITY_ID: "6139",
            CONF_STATION_ID: station_id,
        },
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the entry with the two stations of La Roda de Andalucía."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Spain fuel prices",
        data={},
        subentries_data=[
            _station("Repsol La Roda de Andalucía", "7370"),
            _station("Shell La Roda de Andalucía", "6440"),
        ],
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Do not set up the entry in config flow tests."""
    with patch(
        "homeassistant.components.geoportal_gasolineras.async_setup_entry",
        return_value=None,
    ) as mock:
        yield mock


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock the API client."""
    with (
        patch(
            "homeassistant.components.geoportal_gasolineras.coordinator.PreciosCarburantes",
            autospec=True,
        ) as client_class,
        patch(
            "homeassistant.components.geoportal_gasolineras.config_flow.PreciosCarburantes",
            new=client_class,
        ),
    ):
        client = client_class.return_value
        client.get_provinces.return_value = [
            Province.from_api(item)
            for item in load_json_array_fixture("provincias.json", DOMAIN)
        ]
        client.get_municipalities.return_value = [
            Municipality.from_api(item)
            for item in load_json_array_fixture("municipios.json", DOMAIN)
        ]
        client.get_stations_by_municipality.return_value = StationList.from_api(
            load_json_object_fixture("estaciones.json", DOMAIN)
        )
        yield client
