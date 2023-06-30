"""Tests for the SkyBell integration."""

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

USERNAME = "user"
PASSWORD = "password"
USER_ID = "123456789012345678901234"

CONF_CONFIG_FLOW = {
    CONF_EMAIL: USERNAME,
    CONF_PASSWORD: PASSWORD,
}
