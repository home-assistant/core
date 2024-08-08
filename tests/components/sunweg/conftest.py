"""Conftest for SunWEG tests."""

from datetime import datetime
from unittest.mock import DEFAULT, patch

import pytest
from sunweg.device import MPPT, Inverter, Phase, String
from sunweg.plant import Plant
from sunweg.util import Status


@pytest.fixture
def string_fixture() -> String:
    """Define String fixture."""
    return String("STR1", 450.3, 23.4, 0)


@pytest.fixture
def string_fixture_alternative() -> String:
    """Define String alternative fixture."""
    return String("STR1A", 450.3, 23.4, 0)


@pytest.fixture
def mppt_fixture(string_fixture) -> MPPT:
    """Define MPPT fixture."""
    mppt = MPPT("mppt")
    mppt.strings.append(string_fixture)
    return mppt


@pytest.fixture
def mppt_fixture_alternative(string_fixture_alternative) -> MPPT:
    """Define MPPT alternative fixture."""
    mppt = MPPT("mppt")
    mppt.strings.append(string_fixture_alternative)
    return mppt


@pytest.fixture
def phase_fixture() -> Phase:
    """Define Phase fixture."""
    return Phase("PhaseA", 120.0, 3.2, 0, 0)


@pytest.fixture
def phase_fixture_alternative() -> Phase:
    """Define Phase alternative fixture."""
    return Phase("PhaseAlt", 120.0, 3.2, 0, 0)


@pytest.fixture
def inverter_fixture(phase_fixture, mppt_fixture) -> Inverter:
    """Define inverter fixture."""
    inverter = Inverter(
        21255,
        "INVERSOR01",
        "J63T233018RE074",
        Status.OK,
        23.2,
        0.0,
        "MWh",
        0.0,
        "kWh",
        0,
        0.0,
        1,
        "kW",
    )
    inverter.phases.append(phase_fixture)
    inverter.mppts.append(mppt_fixture)
    return inverter


@pytest.fixture
def inverter_fixture_alternative(
    phase_fixture_alternative, mppt_fixture_alternative
) -> Inverter:
    """Define inverter alternative fixture."""
    inverter = Inverter(
        21255,
        "INVERSOR01",
        "J63T233018RE074",
        Status.OK,
        23.2,
        0.0,
        "MWh",
        0.0,
        "kWh",
        0,
        0.0,
        1,
        "kW",
    )
    inverter.phases.append(phase_fixture_alternative)
    inverter.mppts.append(mppt_fixture_alternative)
    return inverter


@pytest.fixture
def inverter_fixture_invalid() -> Inverter:
    """Define inverter fixture with different id."""
    return Inverter(
        21256,
        "INVERSOR01",
        "J63T233018RE074",
        Status.OK,
        23.2,
        0.0,
        "MWh",
        0.0,
        "kWh",
        0,
        0.0,
        1,
        "kW",
    )


@pytest.fixture
def plant_fixture(inverter_fixture) -> Plant:
    """Define Plant fixture."""
    plant = Plant(
        123456,
        "Plant #123",
        29.5,
        0.5,
        0,
        12.786912,
        24.0,
        "kWh",
        332.2,
        0.012296,
        datetime(2023, 2, 16, 14, 22, 37),
    )
    plant.inverters.append(inverter_fixture)
    return plant


@pytest.fixture
def plant_fixture_alternative(inverter_fixture_alternative) -> Plant:
    """Define Plant alternative fixture."""
    plant = Plant(
        123456,
        "Plant #123",
        29.5,
        0.5,
        0,
        12.786912,
        24.0,
        "kWh",
        332.2,
        0.012296,
        None,
    )
    plant.inverters.append(inverter_fixture_alternative)
    return plant


@pytest.fixture
def plant_fixture_total_power_0() -> Plant:
    """Define Plant fixture."""
    return Plant(
        123456,
        "Plant #123",
        29.5,
        0.5,
        0,
        12.786912,
        24.0,
        "kWh",
        0.0,
        0.012296,
        None,
    )


@pytest.fixture
def plant_fixture_total_power_none() -> Plant:
    """Define Plant fixture."""
    return Plant(
        123456,
        "Plant #123",
        29.5,
        0.5,
        0,
        12.786912,
        24.0,
        "kWh",
        None,
        0.012296,
        None,
    )


@pytest.fixture
def api_fixture(plant_fixture):
    """Mock APIHelper."""
    with patch.multiple(
        "sunweg.api.APIHelper",
        authenticate=DEFAULT,
        listPlants=DEFAULT,
        plant=DEFAULT,
        complete_inverter=DEFAULT,
    ) as api:
        api["authenticate"].return_value = True
        api["listPlants"].return_value = [plant_fixture]
        api["plant"].return_value = plant_fixture
        yield api
