"""Constants for Invoxia (unofficial) test files."""

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

TEST_CONF = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}

TEST_CONF_REAUTH = {
    CONF_USERNAME: "other-username",
    CONF_PASSWORD: "other-password",
}
