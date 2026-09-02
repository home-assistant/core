"""Tests for the Ecowitt WS90 integration."""

from ecowitt_ws90_modbus.testing import WS90_UNIT_ID

from homeassistant.components.ecowitt_ws90.const import CONF_UNIT_ID
from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_HOST = "192.168.1.100"
# The device_id WS90_LIVE_EXAMPLE decodes to; see that library's own
# test_device_info.test_decodes_identity.
MOCK_DEVICE_ID = "12345678"

MOCK_USER_INPUT = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: 502,
    CONF_UNIT_ID: WS90_UNIT_ID,
}
