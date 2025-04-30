"""Tests for the Vogel's MotionMount integration."""

from ipaddress import ip_address

from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

HOST = "192.168.1.31"
PORT = 23
MAC = bytes.fromhex("c4dd57f8a55f")

TVM_ZEROCONF_SERVICE_TYPE = "_tvm._tcp.local."

ZEROCONF_NAME = "My MotionMount"
ZEROCONF_HOST = HOST
ZEROCONF_HOSTNAME = "MMF8A55F.local."
ZEROCONF_PORT = PORT
ZEROCONF_MAC = "c4:dd:57:f8:a5:5f"

MOCK_USER_INPUT = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
}

MOCK_PIN_INPUT = {CONF_PIN: 1234}

MOCK_ZEROCONF_TVM_SERVICE_INFO_V1 = ZeroconfServiceInfo(
    type=TVM_ZEROCONF_SERVICE_TYPE,
    name=f"{ZEROCONF_NAME}.{TVM_ZEROCONF_SERVICE_TYPE}",
    ip_address=ip_address(ZEROCONF_HOST),
    ip_addresses=[ip_address(ZEROCONF_HOST)],
    hostname=ZEROCONF_HOSTNAME,
    port=ZEROCONF_PORT,
    properties={"txtvers": "1", "model": "TVM 7675"},
)

MOCK_ZEROCONF_TVM_SERVICE_INFO_V2 = ZeroconfServiceInfo(
    type=TVM_ZEROCONF_SERVICE_TYPE,
    name=f"{ZEROCONF_NAME}.{TVM_ZEROCONF_SERVICE_TYPE}",
    ip_address=ip_address(ZEROCONF_HOST),
    ip_addresses=[ip_address(ZEROCONF_HOST)],
    hostname=ZEROCONF_HOSTNAME,
    port=ZEROCONF_PORT,
    properties={"mac": ZEROCONF_MAC, "txtvers": "2", "model": "TVM 7675"},
)
