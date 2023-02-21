"""Test the Formula 1 core."""
from datetime import date, datetime
from unittest.mock import patch

import ergast_py
import pytest

from homeassistant import config_entries
from homeassistant.components.formula_one import F1Data
from homeassistant.components.formula_one.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

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
MOCK_CONSTRUCTOR = ergast_py.Constructor(
    constructor_id="mg", url="", name="MG", nationality="British"
)
MOCK_DRIVER_STANDING = ergast_py.DriverStanding(
    position=1,
    position_text="1",
    points=1.0,
    wins=1,
    driver=MOCK_DRIVER,
    constructors=[MOCK_CONSTRUCTOR],
)
MOCK_DRIVER_STANDING_LIST = ergast_py.StandingsList(
    season=2022,
    round_no=1,
    driver_standings=[MOCK_DRIVER_STANDING],
    constructor_standings=[],
)
MOCK_CONSTRUCTOR_STANDING = ergast_py.ConstructorStanding(
    position=1,
    position_text="1",
    points=1.0,
    wins=1,
    constructor=MOCK_CONSTRUCTOR,
)
MOCK_CONSTRUCTOR_STANDING_LIST = ergast_py.StandingsList(
    season=2022,
    round_no=1,
    driver_standings=[],
    constructor_standings=[MOCK_CONSTRUCTOR_STANDING],
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
    date=datetime.now(),
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


async def test_setup_unload_integration(hass: HomeAssistant) -> None:
    """Test we can setup the integration."""

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
        mock_config_entry: config_entries.ConfigEntry = MockConfigEntry(
            domain=DOMAIN,
            data={},
            title="Formula 1",
        )
        mock_config_entry.add_to_hass(hass)

        setup = await hass.config_entries.async_setup(mock_config_entry.entry_id)

        assert setup is True

        unload = await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert unload is True


async def test_f1data_update_failed_too_few_races(hass: HomeAssistant) -> None:
    """Test we handle a failed update."""

    f1_data = F1Data(hass)

    with patch(
        "ergast_py.Ergast.get_constructor_standings",
        return_value=[MOCK_CONSTRUCTOR_STANDING_LIST],
    ), patch(
        "ergast_py.Ergast.get_driver_standings",
        return_value=[MOCK_DRIVER_STANDING_LIST],
    ), patch(
        "ergast_py.Ergast.get_races",
        return_value=[],
    ), pytest.raises(
        UpdateFailed
    ):
        await f1_data.update()


async def test_f1data_update_failed_constructor_standings(hass: HomeAssistant) -> None:
    """Test we throw an UpdateFailed if data fetch fails."""

    f1_data = F1Data(hass)

    with patch(
        "ergast_py.Ergast.get_constructor_standings",
        side_effect=Exception,
    ), patch(
        "ergast_py.Ergast.get_driver_standings",
        return_value=[MOCK_DRIVER_STANDING],
    ), patch(
        "ergast_py.Ergast.get_races",
        return_value=[MOCK_RACE],
    ), pytest.raises(
        UpdateFailed
    ):
        await f1_data.update()


async def test_f1data_update_failed_driver_standings(hass: HomeAssistant) -> None:
    """Test we throw an UpdateFailed if data fetch fails."""

    f1_data = F1Data(hass)

    with patch(
        "ergast_py.Ergast.get_constructor_standings",
        return_value=[MOCK_CONSTRUCTOR_STANDING],
    ), patch(
        "ergast_py.Ergast.get_driver_standings",
        side_effect=Exception,
    ), patch(
        "ergast_py.Ergast.get_races",
        return_value=[MOCK_RACE],
    ), pytest.raises(
        UpdateFailed
    ):
        await f1_data.update()


async def test_f1data_update_failed_races(hass: HomeAssistant) -> None:
    """Test we throw an UpdateFailed if data fetch fails."""

    f1_data = F1Data(hass)

    with patch(
        "ergast_py.Ergast.get_constructor_standings",
        return_value=[MOCK_CONSTRUCTOR_STANDING],
    ), patch(
        "ergast_py.Ergast.get_driver_standings",
        return_value=[MOCK_DRIVER_STANDING],
    ), patch(
        "ergast_py.Ergast.get_races",
        side_effect=Exception,
    ), pytest.raises(
        UpdateFailed
    ):
        await f1_data.update()


async def test_f1data_test_connect_true(hass: HomeAssistant) -> None:
    """Test the behavior of test_connect."""

    f1_data: F1Data = F1Data(hass)

    with patch(
        "ergast_py.Ergast.get_constructor_standings",
        return_value=[MOCK_CONSTRUCTOR_STANDING],
    ):
        test_result = await f1_data.test_connect()

    assert test_result is True


async def test_f1data_test_connect_false(hass: HomeAssistant) -> None:
    """Test the behavior of test_connect."""

    f1_data: F1Data = F1Data(hass)

    with patch(
        "ergast_py.Ergast.get_constructor_standings",
        side_effect=Exception,
    ):
        test_result = await f1_data.test_connect()

    assert test_result is False


async def test_f1data_all_constructor_positions(hass: HomeAssistant) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

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
        await f1_data.update()

    assert f1_data.all_constructor_positions() == {1}


async def test_f1data_all_constructor_ids(hass: HomeAssistant) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

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
        await f1_data.update()

    assert f1_data.all_constructor_ids() == {"mg"}


async def test_f1data_all_driver_positions(hass: HomeAssistant) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

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
        await f1_data.update()

    assert f1_data.all_driver_positions() == {1}


async def test_f1data_all_driver_ids(hass: HomeAssistant) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

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
        await f1_data.update()

    assert f1_data.all_driver_ids() == {"john_smith"}


async def test_f1data_get_driver_name_none(hass: HomeAssistant) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

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
        await f1_data.update()

    assert f1_data.get_driver_name("nobody") is None


async def test_f1data_get_constructor_standing_by_id_none(hass: HomeAssistant) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

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
        await f1_data.update()

    assert f1_data.get_constructor_standing_by_id("nobody") is None


async def test_f1data_get_constructor_standing_by_position_none(
    hass: HomeAssistant,
) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

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
        await f1_data.update()

    assert f1_data.get_constructor_standing_by_position("999") is None


async def test_f1data_get_driver_standing_by_position_none(
    hass: HomeAssistant,
) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

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
        await f1_data.update()

    assert f1_data.get_driver_standing_by_position("999") is None


async def test_f1data_get_race_by_round_none(
    hass: HomeAssistant,
) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

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
        await f1_data.update()

    assert f1_data.get_race_by_round(999) is None


async def test_f1data_get_next_race_none(
    hass: HomeAssistant,
) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

    mock_race = ergast_py.Race(
        season=2022,
        round_no=1,
        url="",
        race_name="Grand Prix",
        circuit=MOCK_CIRCUIT,
        date=datetime(
            year=1900, month=1, day=1, hour=1, minute=1, second=1, microsecond=1
        ),
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

    with patch(
        "ergast_py.Ergast.get_constructor_standings",
        return_value=[MOCK_CONSTRUCTOR_STANDING_LIST],
    ), patch(
        "ergast_py.Ergast.get_driver_standings",
        return_value=[MOCK_DRIVER_STANDING_LIST],
    ), patch(
        "ergast_py.Ergast.get_races",
        return_value=[mock_race],
    ):
        await f1_data.update()

    assert f1_data.get_next_race() is None


async def test_f1data_get_next_race(
    hass: HomeAssistant,
) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

    mock_race = ergast_py.Race(
        season=2022,
        round_no=1,
        url="",
        race_name="Grand Prix",
        circuit=MOCK_CIRCUIT,
        date=datetime(
            year=datetime.now().year + 1,
            month=1,
            day=1,
            hour=1,
            minute=1,
            second=1,
            microsecond=1,
        ),
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

    with patch(
        "ergast_py.Ergast.get_constructor_standings",
        return_value=[MOCK_CONSTRUCTOR_STANDING_LIST],
    ), patch(
        "ergast_py.Ergast.get_driver_standings",
        return_value=[MOCK_DRIVER_STANDING_LIST],
    ), patch(
        "ergast_py.Ergast.get_races",
        return_value=[mock_race],
    ):
        await f1_data.update()

    assert f1_data.get_next_race() == mock_race


async def test_f1data_new_sensors_discovered_new_driver(
    hass: HomeAssistant,
) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

    mock_driver_2 = ergast_py.Driver(
        driver_id="jane_doe",
        code="DOE",
        url="",
        given_name="Jane",
        family_name="Doe",
        date_of_birth=date(year=1900, month=1, day=1),
        nationality="British",
        permanent_number="101",
    )

    mock_driver_2_standing = ergast_py.DriverStanding(
        position=2,
        position_text="2",
        points=2.0,
        wins=0,
        driver=mock_driver_2,
        constructors=[MOCK_CONSTRUCTOR],
    )

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
        await f1_data.update()

    new_drivers = [MOCK_DRIVER_STANDING, mock_driver_2_standing]

    assert (
        f1_data.new_sensors_discovered(
            [MOCK_CONSTRUCTOR_STANDING], new_drivers, [MOCK_RACE]
        )
        is True
    )


async def test_f1data_new_sensors_discovered_new_race(
    hass: HomeAssistant,
) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

    mock_race_2 = ergast_py.Race(
        season=2022,
        round_no=2,
        url="",
        race_name="Grand Prix 2",
        circuit=MOCK_CIRCUIT,
        date=datetime.now(),
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
        await f1_data.update()

    new_races = [MOCK_RACE, mock_race_2]

    assert (
        f1_data.new_sensors_discovered(
            [MOCK_CONSTRUCTOR_STANDING], [MOCK_DRIVER_STANDING], new_races
        )
        is True
    )


async def test_f1data_new_sensors_discovered_false(
    hass: HomeAssistant,
) -> None:
    """Test all_constructor_positions()."""

    f1_data: F1Data = F1Data(hass)

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
        await f1_data.update()

    assert (
        f1_data.new_sensors_discovered(
            [MOCK_CONSTRUCTOR_STANDING], [MOCK_DRIVER_STANDING], [MOCK_RACE]
        )
        is False
    )
