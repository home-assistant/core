"""Tests for IAMMETER."""

from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_INPUT = {CONF_HOST: "192.0.2.1", CONF_PORT: 80}
MOCK_DATA = {
    "Model": "WEM3080",
    "sn": "test-meter",
    "mac": "00:00:00:00:00:01",
    "Voltage": 230.0,
    "Current": 2.0,
    "Power": 460.0,
    "ImportEnergy": 100.0,
    "ExportGrid": 10.0,
}
