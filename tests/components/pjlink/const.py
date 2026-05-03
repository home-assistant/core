"""Constants for the PJLink tests."""

from homeassistant.components.pjlink.const import (
    CONF_ENCODING,
    DEFAULT_ENCODING,
    DEFAULT_PORT,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT

DEFAULT_DATA = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_PASSWORD: "test-password",
}
DEFAULT_DATA_WO_PORT = {CONF_HOST: "1.1.1.1", CONF_PASSWORD: "test-password"}
DEFAULT_DATA_W_ENCODING = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_PASSWORD: "test-password",
    CONF_ENCODING: DEFAULT_ENCODING,
}
