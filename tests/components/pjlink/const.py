"""Constants for the PJLink tests."""

from homeassistant.components.pjlink.const import DEFAULT_PORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT

DEFAULT_DATA = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_PASSWORD: "test-password",
}
