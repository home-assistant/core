"""Common functions needed to setup tests for Sun WEG."""
from datetime import datetime

from sunweg.device import MPPT, Inverter, Phase, String
from sunweg.plant import Plant

from homeassistant.components.sunweg.const import CONF_PLANT_ID, DOMAIN
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}

SUNWEG_PLANT_RESPONSE = Plant(
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

SUNWEG_INVERTER_RESPONSE = Inverter(
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

SUNWEG_PHASE_RESPONSE = Phase("PhaseA", 120.0, 3.2, 0, 0)

SUNWEG_MPPT_RESPONSE = MPPT("MPPT1")

SUNWEG_STRING_RESPONSE = String("STR1", 450.3, 23.4, 0)

SUNWEG_LOGIN_RESPONSE = True

SUNWEG_MOCK_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    data={
        CONF_USERNAME: "user@email.com",
        CONF_PASSWORD: "password",
        CONF_PLANT_ID: 0,
        CONF_NAME: "Name",
    },
)
