"""Tests for the KACO RS485 integration."""

from homeassistant.components.kaco_rs485.const import (
    CONF_ADDRESSES,
    CONF_INVERTERS,
    CONF_SW_VERSION,
)
from homeassistant.const import CONF_MODEL, CONF_PORT

MOCK_PORT = "/dev/ttyUSB0"
MOCK_PORT_DESCRIPTION = "AtomS3 Lite RS485 (RS-485)"

# 6400xi at 1 and 2, 8000xi at 4 — the layout the captured frames came from.
MOCK_ADDRESSES = [1, 2, 4]

MOCK_ENTRY_DATA = {
    CONF_PORT: MOCK_PORT,
    CONF_ADDRESSES: MOCK_ADDRESSES,
    CONF_INVERTERS: {
        "1": {CONF_MODEL: "6400xi", CONF_SW_VERSION: "K222.36DE 6817"},
        "2": {CONF_MODEL: "6400xi", CONF_SW_VERSION: "K222.36DE 6817"},
        "4": {CONF_MODEL: "8000xi", CONF_SW_VERSION: "K222.36DE 1C5F"},
    },
}
