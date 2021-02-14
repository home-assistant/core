"""Tests for the Keenetic NDMS2 component."""
from homeassistant.components.keenetic_ndms2 import const
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)

MOCK_NAME = "Keenetic Ultra 2030"

MOCK_DATA = {
    CONF_HOST: "0.0.0.0",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_PORT: 23,
}

MOCK_OPTIONS = {
    CONF_SCAN_INTERVAL: 15,
    const.CONF_CONSIDER_HOME: 150,
    const.CONF_TRY_HOTSPOT: False,
    const.CONF_INCLUDE_ARP: True,
    const.CONF_INCLUDE_ASSOCIATED: True,
    const.CONF_INTERFACES: ["Home", "VPS0"],
}
