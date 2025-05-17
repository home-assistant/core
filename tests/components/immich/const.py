"""Constants for the Immich integration tests."""

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)

MOCK_USER_DATA = {
    CONF_HOST: "localhost",
    CONF_API_KEY: "abcdef0123456789",
    CONF_PORT: 80,
    CONF_SSL: False,
    CONF_VERIFY_SSL: False,
}
