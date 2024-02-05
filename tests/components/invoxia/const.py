"""Constants for Invoxia (unofficial) test files."""

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

TEST_CONF = {
    CONF_EMAIL: "test-user@domain.ha",
    CONF_PASSWORD: "test-password",
}

TEST_CONF_REAUTH = {
    CONF_EMAIL: "other.user@domain.ha",
    CONF_PASSWORD: "other-password",
}
