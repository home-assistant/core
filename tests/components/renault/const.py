"""Constants for the Renault integration tests."""
from homeassistant.components.renault.const import CONF_KAMEREON_ACCOUNT_ID, CONF_LOCALE
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

# Mock config data to be used across multiple tests
MOCK_CONFIG = {
    CONF_USERNAME: "email@test.com",
    CONF_PASSWORD: "test",
    CONF_KAMEREON_ACCOUNT_ID: "account_id_1",
    CONF_LOCALE: "fr_FR",
}
