"""Test the Formula 1 sensors."""
from datetime import date, datetime, timedelta
from unittest.mock import patch

import ergast_py

from homeassistant import config_entries
from homeassistant.components.formula_one.const import DOMAIN, F1_STATE_MULTIPLE
from homeassistant.components.formula_one.coordinator import F1UpdateCoordinator
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry

MOCK_DRIVER = ergast_py.Driver(
    driver_id="john_smith",
    code="SMI",
    url="",
    given_name="John",
    family_name="Smith",
    date_of_birth=date(year=1900, month=1, day=1),
    nationality="British",
    permanent_number="100",
)
MOCK_DRIVER_2 = ergast_py.Driver(
    driver_id="jane_doe",
    code="DOE",
    url="",
    given_name="Jane",
    family_name="Doe",
    date_of_birth=date(year=1900, month=1, day=2),
    nationality="British",
    permanent_number="101",
)
MOCK_DRIVER_3 = ergast_py.Driver(
    driver_id="driver_three",
    code="THR",
    url="",
    given_name="Driver",
    family_name="Three",
    date_of_birth=date(year=1900, month=1, day=3),
    nationality="British",
    permanent_number="102",
)
MOCK_CONSTRUCTOR = ergast_py.Constructor(
    constructor_id="mg", url="", name="MG", nationality="British"
)
MOCK_CONSTRUCTOR_2 = ergast_py.Constructor(
    constructor_id="delorian", url="", name="DEL", nationality="British"
)
MOCK_DRIVER_STANDING = ergast_py.DriverStanding(
    position=1,
    position_text="1",
    points=1.0,
    wins=1,
    driver=MOCK_DRIVER,
    constructors=[MOCK_CONSTRUCTOR],
)
MOCK_DRIVER_STANDING_2 = ergast_py.DriverStanding(
    position=2,
    position_text="2",
    points=0.0,
    wins=0,
    driver=MOCK_DRIVER_2,
    constructors=[MOCK_CONSTRUCTOR_2],
)
MOCK_DRIVER_STANDING_3 = ergast_py.DriverStanding(
    position=1,
    position_text="1",
    points=0.0,
    wins=0,
    driver=MOCK_DRIVER_3,
    constructors=[MOCK_CONSTRUCTOR, MOCK_CONSTRUCTOR_2],
)
MOCK_DRIVER_STANDING_LIST = ergast_py.StandingsList(
    season=2022,
    round_no=1,
    driver_standings=[MOCK_DRIVER_STANDING],
    constructor_standings=[],
)
MOCK_DRIVER_STANDING_LIST_2 = ergast_py.StandingsList(
    season=2022,
    round_no=1,
    driver_standings=[MOCK_DRIVER_STANDING, MOCK_DRIVER_STANDING_2],
    constructor_standings=[],
)
MOCK_DRIVER_STANDING_LIST_3 = ergast_py.StandingsList(
    season=2022,
    round_no=1,
    driver_standings=[MOCK_DRIVER_STANDING_3],
    constructor_standings=[],
)
MOCK_CONSTRUCTOR_STANDING = ergast_py.ConstructorStanding(
    position=1,
    position_text="1",
    points=1.0,
    wins=1,
    constructor=MOCK_CONSTRUCTOR,
)
MOCK_CONSTRUCTOR_STANDING_2 = ergast_py.ConstructorStanding(
    position=2,
    position_text="2",
    points=0.0,
    wins=0,
    constructor=MOCK_CONSTRUCTOR_2,
)
MOCK_CONSTRUCTOR_STANDING_LIST = ergast_py.StandingsList(
    season=2022,
    round_no=1,
    driver_standings=[],
    constructor_standings=[MOCK_CONSTRUCTOR_STANDING],
)
MOCK_CONSTRUCTOR_STANDING_LIST_2 = ergast_py.StandingsList(
    season=2022,
    round_no=2,
    driver_standings=[],
    constructor_standings=[MOCK_CONSTRUCTOR_STANDING_2],
)
MOCK_LOCATION = ergast_py.Location(
    latitude=0.0, longitude=0.0, locality="here", country="UK"
)
MOCK_CIRCUIT = ergast_py.Circuit(
    circuit_id="tt", url="", circuit_name="The Track", location=MOCK_LOCATION
)
MOCK_RACE = ergast_py.Race(
    season=2022,
    round_no=1,
    url="",
    race_name="Grand Prix",
    circuit=MOCK_CIRCUIT,
    date=datetime.now() + timedelta(days=1),
    results=[],
    first_practice=datetime.now(),
    second_practice=datetime.now(),
    third_practice=datetime.now(),
    sprint=datetime.now(),
    sprint_results=[],
    qualifying=datetime.now(),
    qualifying_results=[],
    pit_stops=[],
    laps=[],
)
MOCK_RACE_2 = ergast_py.Race(
    season=2022,
    round_no=2,
    url="",
    race_name="Grand Prix Deux",
    circuit=MOCK_CIRCUIT,
    date=datetime.now() + timedelta(days=2),
    results=[],
    first_practice=datetime.now(),
    second_practice=datetime.now(),
    third_practice=datetime.now(),
    sprint=datetime.now(),
    sprint_results=[],
    qualifying=datetime.now(),
    qualifying_results=[],
    pit_stops=[],
    laps=[],
)


async def test_sensors_unavailable(hass: HomeAssistant) -> None:
    """Test we get None if requesting an invalid position."""

    # setup the integration with 2 sensors each
    with patch(
        "ergast_py.Ergast.get_constructor_standings",
        return_value=[MOCK_CONSTRUCTOR_STANDING_LIST_2],
    ), patch(
        "ergast_py.Ergast.get_driver_standings",
        return_value=[MOCK_DRIVER_STANDING_LIST_2],
    ), patch(
        "ergast_py.Ergast.get_races",
        return_value=[MOCK_RACE, MOCK_RACE_2],
    ):
        mock_config_entry: config_entries.ConfigEntry = MockConfigEntry(
            domain=DOMAIN,
            data={},
            title="Formula 1",
        )
        mock_config_entry.add_to_hass(hass)

        setup = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert setup is True

    coordinator: F1UpdateCoordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    # refresh with new data having second sensors missing
    with patch(
        "ergast_py.Ergast.get_constructor_standings",
        return_value=[MOCK_CONSTRUCTOR_STANDING_LIST],
    ), patch(
        "ergast_py.Ergast.get_driver_standings",
        return_value=[MOCK_DRIVER_STANDING_LIST],
    ), patch(
        "ergast_py.Ergast.get_races",
        return_value=[MOCK_RACE],
    ):
        await coordinator.async_refresh()

    # verify second sensors are unavailable
    con_pos_2_state: State = hass.states.get("sensor.f1_constructor_2")
    dri_pos_2_state: State = hass.states.get("sensor.f1_driver_2")
    race_2_state: State = hass.states.get("sensor.f1_race_2")

    assert con_pos_2_state is None
    assert dri_pos_2_state is None
    assert race_2_state is None


async def test_driver_multiple_constructors(hass: HomeAssistant) -> None:
    """Test we get F1_STATE_MULTIPLE if a driver has multiple constructors."""

    with patch(
        "ergast_py.Ergast.get_constructor_standings",
        return_value=[MOCK_CONSTRUCTOR_STANDING_LIST],
    ), patch(
        "ergast_py.Ergast.get_driver_standings",
        return_value=[MOCK_DRIVER_STANDING_LIST_3],
    ), patch(
        "ergast_py.Ergast.get_races",
        return_value=[MOCK_RACE],
    ):
        mock_config_entry: config_entries.ConfigEntry = MockConfigEntry(
            domain=DOMAIN,
            data={},
            title="Formula 1",
        )
        mock_config_entry.add_to_hass(hass)

        setup = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert setup is True
    assert (
        hass.states.get("sensor.f1_driver_01").attributes["team"] == F1_STATE_MULTIPLE
    )


async def test_unique_id_and_name_generators(hass: HomeAssistant) -> None:
    """Test our unique_id and name generators."""
    const_list = generate_constructor_standings_list()
    driv_list = generate_driver_standings_list()
    races = generate_ten_races()

    with patch(
        "ergast_py.Ergast.get_constructor_standings",
        return_value=[const_list],
    ), patch(
        "ergast_py.Ergast.get_driver_standings",
        return_value=[driv_list],
    ), patch(
        "ergast_py.Ergast.get_races",
        return_value=races,
    ):
        mock_config_entry: config_entries.ConfigEntry = MockConfigEntry(
            domain=DOMAIN,
            data={},
            title="Formula 1",
        )
        mock_config_entry.add_to_hass(hass)

        setup = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert setup is True

    assert hass.states.get("sensor.f1_driver_01") is not None
    assert hass.states.get("sensor.f1_driver_10") is not None

    assert hass.states.get("sensor.f1_driver_01").name == "F1 Driver 01"
    assert hass.states.get("sensor.f1_driver_10").name == "F1 Driver 10"

    assert hass.states.get("sensor.f1_constructor_01") is not None
    assert hass.states.get("sensor.f1_constructor_10") is not None

    assert hass.states.get("sensor.f1_constructor_01").name == "F1 Constructor 01"
    assert hass.states.get("sensor.f1_constructor_10").name == "F1 Constructor 10"

    assert hass.states.get("sensor.f1_race_01") is not None
    assert hass.states.get("sensor.f1_race_10") is not None

    assert hass.states.get("sensor.f1_race_01").name == "F1 Race 01"
    assert hass.states.get("sensor.f1_race_10").name == "F1 Race 10"


def generate_ten_drivers() -> list[ergast_py.Driver]:
    """Generate a lot of drivers."""
    ret: list[ergast_py.Driver] = []

    for i in range(0, 10):
        ret.append(
            ergast_py.Driver(
                driver_id=f"driver_{i}",
                code=f"D{i}",
                url="",
                given_name="Driver",
                family_name=f"Family{i}",
                date_of_birth=date(2020, 1, 1),
                nationality="British",
                permanent_number=f"{i}",
            )
        )

    return ret


def generate_ten_constructors() -> list[ergast_py.Constructor]:
    """Generate a lot of constructors."""
    ret: list[ergast_py.Constructor] = []

    for i in range(0, 10):
        ret.append(
            ergast_py.Constructor(
                constructor_id=f"constr_{i}",
                url="",
                name=f"Constructor {i}",
                nationality="British",
            )
        )

    return ret


def generate_ten_driver_standings() -> list[ergast_py.DriverStanding]:
    """Generate driver standings for drivers."""
    ret: list[ergast_py.DriverStanding] = []

    drivers = generate_ten_drivers()
    constructors = generate_ten_constructors()

    assert len(drivers) == len(constructors)

    for i, driver in enumerate(drivers):
        ipo = i + 1
        ret.append(
            ergast_py.DriverStanding(
                position=ipo,
                position_text=f"{ipo}",
                points=float(ipo),
                wins=10 - i,
                driver=driver,
                constructors=[constructors[i]],
            )
        )

    return ret


def generate_ten_constructor_standings() -> list[ergast_py.ConstructorStanding]:
    """Generate constructor standings for constructors."""
    ret: list[ergast_py.ConstructorStanding] = []

    constructors = generate_ten_constructors()

    for i, constructor in enumerate(constructors):
        ipo = i + 1
        ret.append(
            ergast_py.ConstructorStanding(
                position=ipo,
                position_text=f"{ipo}",
                points=i,
                wins=10 - i,
                constructor=constructor,
            )
        )

    return ret


def generate_driver_standings_list() -> ergast_py.StandingsList:
    """Generate driver standings lists."""
    driver_standings = generate_ten_driver_standings()

    return ergast_py.StandingsList(
        season=2022,
        round_no=10,
        driver_standings=driver_standings,
        constructor_standings=[],
    )


def generate_constructor_standings_list() -> ergast_py.StandingsList:
    """Generate constructor standings lists."""
    constructor_standings = generate_ten_constructor_standings()

    return ergast_py.StandingsList(
        season=2022,
        round_no=10,
        driver_standings=[],
        constructor_standings=constructor_standings,
    )


def generate_ten_races() -> list[ergast_py.Race]:
    """Generate some mock Races."""
    ret: list[ergast_py.Race] = []

    for i in range(0, 10):
        ret.append(
            ergast_py.Race(
                season=2022,
                round_no=i + 1,
                url="",
                race_name=f"Grand Prix {i}",
                circuit=MOCK_CIRCUIT,
                date=datetime.now() + timedelta(days=i + 1),
                results=[],
                first_practice=datetime.now(),
                second_practice=datetime.now(),
                third_practice=datetime.now(),
                sprint=datetime.now(),
                sprint_results=[],
                qualifying=datetime.now(),
                qualifying_results=[],
                pit_stops=[],
                laps=[],
            )
        )

    return ret
