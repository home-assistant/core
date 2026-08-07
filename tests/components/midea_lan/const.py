"""Constants for Midea LAN tests."""

from midealocal.const import ProtocolVersion

from homeassistant.components.midea_lan.const import CONF_KEY, CONF_SUBTYPE
from homeassistant.components.midea_lan.device_catalog import MIDEA_DEVICE_NAMES
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_MODEL,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOKEN,
    CONF_TYPE,
)

TEST_DEVICE_ID = 12345678
TEST_IP_ADDRESS = "1.1.1.1"
TEST_KEY = "bb" * 16
TEST_MODEL = "MSAGBU-09HRFN8"
TEST_NAME = "Bedroom AC"
TEST_PORT = 6444
TEST_PROTOCOL = ProtocolVersion.V3
TEST_SUBTYPE = 0
TEST_TOKEN = "aa" * 16
TEST_TYPE = next(iter(MIDEA_DEVICE_NAMES))

BASE_DATA = {
    CONF_DEVICE_ID: TEST_DEVICE_ID,
    CONF_IP_ADDRESS: TEST_IP_ADDRESS,
    CONF_PORT: TEST_PORT,
    CONF_MODEL: TEST_MODEL,
    CONF_PROTOCOL: TEST_PROTOCOL,
}

DISCOVERY_RESULT = {
    TEST_DEVICE_ID: {
        **BASE_DATA,
        CONF_TYPE: TEST_TYPE,
    }
}

EXTENDED_DATA = {
    **BASE_DATA,
    CONF_TYPE: TEST_TYPE,
    CONF_SUBTYPE: TEST_SUBTYPE,
    CONF_TOKEN: TEST_TOKEN,
    CONF_KEY: TEST_KEY,
}
