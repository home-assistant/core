"""Common fixtures for the Data Grand Lyon tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

from data_grand_lyon_ha import (
    TclParkAndRide,
    TclPassage,
    TclPassageType,
    TclStop,
    VelovAvailabilityLevel,
    VelovBikeStandAvailability,
    VelovStation,
    VelovStationStatus,
)
import pytest

from homeassistant.components.data_grand_lyon.const import (
    CONF_LINE,
    CONF_PARK_ID,
    CONF_STATION_ID,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_PARK_AND_RIDE,
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

MOCK_TCL_STOPS = [
    TclStop(
        id=100,
        gid=1100,
        adresse="Place Bellecour",  # codespell:ignore adresse
        ascenseur=False,
        commune="Lyon 2",
        desserte=["C3", "27"],
        escalator=False,
        insee="69382",
        last_update=datetime(2026, 4, 10, 0, 0),
        lat=45.757,
        lon=4.832,
        nom="Bellecour",
        pmr=True,
    ),
    TclStop(
        id=200,
        gid=1200,
        adresse="Cours Lafayette",  # codespell:ignore adresse
        ascenseur=True,
        commune="Lyon 3",
        desserte=["C3", "T1"],
        escalator=True,
        insee="69383",
        last_update=datetime(2026, 4, 10, 0, 0),
        lat=45.763,
        lon=4.846,
        nom="Part-Dieu",
        pmr=True,
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

MOCK_VELOV_STATIONS = [
    MOCK_VELOV_STATION,
    VelovStation(
        number=2002,
        name="Hôtel de Ville",
        address="",
        commune="",
        status=VelovStationStatus.OPEN,
        availability=VelovAvailabilityLevel.GREEN,
        lat=45.767,
        lng=4.835,
        bike_stands=15,
        available_bikes=10,
        available_bike_stands=5,
        banking=True,
        last_update=datetime(2026, 4, 10, 14, 0),
        total_stands=VelovBikeStandAvailability(
            bikes=10,
            electrical_bikes=3,
            electrical_internal_battery_bikes=2,
            electrical_removable_battery_bikes=1,
            mechanical_bikes=7,
            stands=5,
            capacity=15,
        ),
    ),
]


MOCK_PARK_AND_RIDE = TclParkAndRide(
    id="P+R Gorge de Loup",
    gid=10,
    nom="Gorge de Loup",
    capacite=240,
    place_handi=6,
    horaires="24h/24",
    p_surv=True,
    nb_tot_place_dispo=42,
    last_update=datetime(2026, 4, 10, 14, 0),
    last_update_fme=datetime(2026, 4, 10, 13, 55),
)

MOCK_PARK_AND_RIDES = [
    MOCK_PARK_AND_RIDE,
    TclParkAndRide(
        id="P+R Oullins La Saulaie",
        gid=20,
        nom="Oullins La Saulaie",
        capacite=420,
        place_handi=10,
        horaires="5h-1h",
        p_surv=False,
        nb_tot_place_dispo=120,
        last_update=datetime(2026, 4, 10, 14, 0),
        last_update_fme=datetime(2026, 4, 10, 13, 55),
    ),
]


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
def mock_park_and_ride_subentries() -> list[ConfigSubentryData]:
    """Mock park-and-ride subentries."""
    return [
        ConfigSubentryData(
            data={CONF_PARK_ID: "P+R Gorge de Loup"},
            subentry_id="park_1",
            subentry_type=SUBENTRY_TYPE_PARK_AND_RIDE,
            title="Gorge de Loup",
            unique_id="park_and_ride_P+R Gorge de Loup",
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
def mock_park_and_ride_config_entry(
    mock_park_and_ride_subentries: list[ConfigSubentryData],
) -> MockConfigEntry:
    """Create a mock config entry with park-and-ride subentries."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        subentries_data=mock_park_and_ride_subentries,
    )


@pytest.fixture
def mock_tcl_client() -> Generator[AsyncMock]:
    """Mock DataGrandLyonClient for coordinator and config flow."""
    with (
        patch(
            "homeassistant.components.data_grand_lyon.DataGrandLyonClient",
            autospec=True,
        ) as mock_cls,
        patch(
            "homeassistant.components.data_grand_lyon.config_flow.DataGrandLyonClient",
            new=mock_cls,
        ),
    ):
        client = mock_cls.return_value
        client.get_tcl_passages.return_value = MOCK_DEPARTURES
        client.get_tcl_stops.return_value = MOCK_TCL_STOPS
        client.get_velov_stations.return_value = MOCK_VELOV_STATIONS
        client.get_tcl_park_and_rides.return_value = MOCK_PARK_AND_RIDES
        yield client
