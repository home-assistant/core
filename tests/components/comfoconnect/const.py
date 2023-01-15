"""Constants for the Comfoconnect integration tests."""
from homeassistant.components.comfoconnect.const import (
    CONF_USER_AGENT,
    DEFAULT_NAME,
    DEFAULT_PIN,
    DEFAULT_TOKEN,
    DEFAULT_USER_AGENT,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, CONF_TOKEN

COMPONENT = "comfoconnect"

CONF_DATA = {
    CONF_HOST: "127.0.0.1",
    CONF_NAME: DEFAULT_NAME,
    CONF_TOKEN: DEFAULT_TOKEN,
    CONF_PIN: DEFAULT_PIN,
    CONF_USER_AGENT: DEFAULT_USER_AGENT,
}
