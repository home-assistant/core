"""Tests for the Ecowitt WS90 integration."""

from ecowitt_ws90_modbus.testing import WS90_UNIT_ID

from homeassistant.components.ecowitt_ws90.const import CONF_UNIT_ID
from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_HOST = "192.168.1.100"
# f"{WS90_LIVE_EXAMPLE[0x163]:04x}{WS90_LIVE_EXAMPLE[0x164]:04x}"
MOCK_DEVICE_ID = "12345678"

MOCK_USER_INPUT = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: 502,
    CONF_UNIT_ID: WS90_UNIT_ID,
}
