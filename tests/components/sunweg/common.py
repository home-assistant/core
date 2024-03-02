"""Common functions needed to setup tests for Sun WEG."""

from homeassistant.components.sunweg.const import CONF_PLANT_ID, DOMAIN
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

SUNWEG_USER_INPUT = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}

SUNWEG_MOCK_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    data={
        CONF_USERNAME: "user@email.com",
        CONF_PASSWORD: "password",
        CONF_PLANT_ID: 0,
        CONF_NAME: "Name",
    },
)
