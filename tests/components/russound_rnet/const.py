"""Constants for russound_rnet tests."""

from homeassistant.components.russound_rnet.const import (
    CONF_BAUDRATE,
    CONF_MODEL,
    CONF_SOURCES,
    TYPE_SERIAL,
    TYPE_TCP,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE

MODEL = "caa66"

MOCK_SOURCES = {
    "1": "Sonos",
    "2": "TV",
    "3": "Radio",
    "4": "CD",
    "5": "Aux",
    "6": "Tape",
}

MOCK_TCP_STEP_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 9999,
}

MOCK_TCP_CONFIG = {
    CONF_TYPE: TYPE_TCP,
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 9999,
    CONF_MODEL: MODEL,
    CONF_SOURCES: MOCK_SOURCES,
}

MOCK_SERIAL_STEP_INPUT = {
    CONF_DEVICE: "/dev/ttyUSB0",
    CONF_BAUDRATE: 19200,
}

MOCK_SERIAL_CONFIG = {
    CONF_TYPE: TYPE_SERIAL,
    CONF_DEVICE: "/dev/ttyUSB0",
    CONF_BAUDRATE: 19200,
    CONF_MODEL: MODEL,
    CONF_SOURCES: MOCK_SOURCES,
}
