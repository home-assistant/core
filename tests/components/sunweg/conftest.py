"""Conftest for SunWEG tests."""

from datetime import datetime

import pytest
from sunweg.device import MPPT, Inverter, Phase, String
from sunweg.plant import Plant


@pytest.fixture
def string_fixture() -> String:
    """Define String fixture."""
    return String("STR1", 450.3, 23.4, 0)


@pytest.fixture
def mppt_fixture(string_fixture) -> MPPT:
    """Define MPPT fixture."""
    mppt = MPPT("mppt")
    mppt.strings.append(string_fixture)
    return mppt


@pytest.fixture
def phase_fixture() -> Phase:
    """Define Phase fixture."""
    return Phase("PhaseA", 120.0, 3.2, 0, 0)


@pytest.fixture
def inverter_fixture(phase_fixture, mppt_fixture) -> Inverter:
    """Define inverter fixture."""
    inverter = Inverter(
        21255,
        "INVERSOR01",
        "J63T233018RE074",
        23.2,
        0.0,
        0.0,
        "MWh",
        0,
        "kWh",
        0.0,
        1,
        0,
        "kW",
    )
    inverter.phases.append(phase_fixture)
    inverter.mppts.append(mppt_fixture)
    return inverter


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
