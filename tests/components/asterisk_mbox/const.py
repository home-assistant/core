"""Asterisk tests constants."""

from homeassistant.components.asterisk_mbox import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT

CONFIG = {
    DOMAIN: {
        CONF_HOST: "localhost",
        CONF_PASSWORD: "password",
        CONF_PORT: 1234,
    }
}
