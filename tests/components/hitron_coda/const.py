"""Test data for Hitron CODA."""

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TYPE, CONF_USERNAME

CONFIG = {
    CONF_HOST: "192.0.2.1",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "test-password",
    CONF_TYPE: "rogers",
}
MAC = "AA:BB:CC:DD:EE:FF"
NEW_MAC = "11:22:33:44:55:66"
DEVICES = {MAC: "phone"}
