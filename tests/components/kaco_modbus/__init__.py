"""Tests for the KACO Modbus integration."""

from homeassistant.components.kaco_modbus.const import CONF_UNIT_ID
from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_SERIAL = "8.6TL00000000"
MOCK_MODEL = "blueplanet 8.6 TL3 INT"

MOCK_USER_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_UNIT_ID: 1,
}
