"""Constants for Unmanic tests."""
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_VERIFY_SSL,
)

MOCK_CONFIG = {
    CONF_HOST: "127.0.0.2",
    CONF_PORT: 8888,
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
    CONF_TIMEOUT: 8,
}
