"""Test for ViCare."""
from homeassistant.components.vicare.const import CONF_HEATING_TYPE
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)

ENTRY_CONFIG = {
    CONF_USERNAME: "foo@bar.com",
    CONF_PASSWORD: "1234",
    CONF_CLIENT_ID: "5678",
    CONF_HEATING_TYPE: "auto",
    CONF_SCAN_INTERVAL: 60,
    CONF_NAME: "ViCare",
}

MOCK_MAC = "B874241B7B9"
