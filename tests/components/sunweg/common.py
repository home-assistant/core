"""Common functions needed to setup tests for Sun WEG."""
from datetime import datetime

from sunweg.plant import Plant

from homeassistant.components.sunweg.const import CONF_PLANT_ID, DOMAIN
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}

SUNWEG_PLANT_LIST_RESPONSE = [
    Plant(
        123456,
        "Plant #123",
        29.5,
        0.5,
        0,
        12.786912,
        24.0,
        332.2,
        0.012296,
        datetime(2023, 2, 16, 14, 22, 37),
    )
]

SUNWEG_LOGIN_RESPONSE = True

SUNWEG_MOCK_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    data={
        CONF_USERNAME: "user@email.com",
        CONF_PASSWORD: "password",
        CONF_PLANT_ID: 12345,
        CONF_NAME: "Name",
    },
)
