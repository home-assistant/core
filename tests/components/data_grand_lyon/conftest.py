"""Common fixtures for the Data Grand Lyon tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

from data_grand_lyon_ha import (
    TclPassage,
    TclPassageType,
    VelovAvailabilityLevel,
    VelovBikeStandAvailability,
    VelovStation,
    VelovStationStatus,
)
import pytest

from homeassistant.components.data_grand_lyon.const import (
    CONF_LINE,
    CONF_STATION_ID,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
    SUBENTRY_TYPE_VELOV_STATION,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_DEPARTURES = [
    TclPassage(
        id=100,
        ligne="C3",
        direction="Gare Part-Dieu",
        delai_passage="3 min",
        type=TclPassageType.ESTIMATED,
        heure_passage=datetime(2026, 4, 10, 14, 3),
        id_tarret_destination=0,
        course_theorique="A",
    ),
    TclPassage(
        id=100,
        ligne="C3",
        direction="Gare St-Paul",
        delai_passage="8 min",
        type=TclPassageType.THEORETICAL,
        heure_passage=datetime(2026, 4, 10, 14, 8),
        id_tarret_destination=0,
        course_theorique="B",
    ),
]

MOCK_VELOV_STATION = VelovStation(
    number=1001,
    name="Place Bellecour",
    address="Place Bellecour",
    commune="Lyon",
    status=VelovStationStatus.OPEN,
    availability=VelovAvailabilityLevel.GREEN,
    lat=45.757,
    lng=4.832,
    bike_stands=20,
    available_bikes=15,
    available_bike_stands=5,
    banking=True,
    last_update=datetime(2026, 4, 10, 14, 0),
    total_stands=VelovBikeStandAvailability(
        bikes=15,
        electrical_bikes=5,
        electrical_internal_battery_bikes=3,
        electrical_removable_battery_bikes=2,
        mechanical_bikes=10,
        stands=5,
        capacity=20,
    ),
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.data_grand_lyon.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_subentries() -> list[ConfigSubentryData]:
    """Mock subentries."""
    return [
        ConfigSubentryData(
            data={CONF_LINE: "C3", CONF_STOP_ID: 100},
            subentry_id="stop_1",
            subentry_type=SUBENTRY_TYPE_STOP,
            title="C3 - Stop 100",
            unique_id="C3_100",
        )
    ]


@pytest.fixture
def mock_velov_subentries() -> list[ConfigSubentryData]:
    """Mock Vélo'v subentries."""
    return [
        ConfigSubentryData(
            data={CONF_STATION_ID: 1001},
            subentry_id="velov_1",
            subentry_type=SUBENTRY_TYPE_VELOV_STATION,
            title="Vélo'v 1001",
            unique_id="velov_1001",
        )
    ]


@pytest.fixture
def mock_config_entry(
    mock_subentries: list[ConfigSubentryData],
) -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        subentries_data=mock_subentries,
    )


@pytest.fixture
def mock_velov_config_entry(
    mock_velov_subentries: list[ConfigSubentryData],
) -> MockConfigEntry:
    """Create a mock config entry with Vélo'v subentries."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        subentries_data=mock_velov_subentries,
    )


@pytest.fixture
def mock_tcl_client() -> Generator[AsyncMock]:
    """Mock DataGrandLyonClient for coordinator."""
    with patch(
        "homeassistant.components.data_grand_lyon.DataGrandLyonClient", autospec=True
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_tcl_passages.return_value = MOCK_DEPARTURES
        client.get_velov_stations.return_value = [MOCK_VELOV_STATION]
        yield client
