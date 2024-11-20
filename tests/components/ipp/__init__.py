"""Tests for the IPP integration."""

from ipaddress import ip_address

from homeassistant.components import zeroconf
from homeassistant.components.ipp.const import CONF_BASE_PATH
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL

ATTR_HOSTNAME = "hostname"
ATTR_PROPERTIES = "properties"

HOST = "192.168.1.31"
PORT = 631
BASE_PATH = "/ipp/print"

IPP_ZEROCONF_SERVICE_TYPE = "_ipp._tcp.local."
IPPS_ZEROCONF_SERVICE_TYPE = "_ipps._tcp.local."

ZEROCONF_NAME = "EPSON XP-6000 Series"
ZEROCONF_HOST = HOST
ZEROCONF_HOSTNAME = "EPSON123456.local."
ZEROCONF_PORT = PORT
ZEROCONF_RP = "ipp/print"

MOCK_USER_INPUT = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_SSL: False,
    CONF_VERIFY_SSL: False,
    CONF_BASE_PATH: BASE_PATH,
}

MOCK_ZEROCONF_IPP_SERVICE_INFO = zeroconf.ZeroconfServiceInfo(
    type=IPP_ZEROCONF_SERVICE_TYPE,
    name=f"{ZEROCONF_NAME}.{IPP_ZEROCONF_SERVICE_TYPE}",
    ip_address=ip_address(ZEROCONF_HOST),
    ip_addresses=[ip_address(ZEROCONF_HOST)],
    hostname=ZEROCONF_HOSTNAME,
    port=ZEROCONF_PORT,
    properties={"rp": ZEROCONF_RP},
)

MOCK_ZEROCONF_IPPS_SERVICE_INFO = zeroconf.ZeroconfServiceInfo(
    type=IPPS_ZEROCONF_SERVICE_TYPE,
    name=f"{ZEROCONF_NAME}.{IPPS_ZEROCONF_SERVICE_TYPE}",
    ip_address=ip_address(ZEROCONF_HOST),
    ip_addresses=[ip_address(ZEROCONF_HOST)],
    hostname=ZEROCONF_HOSTNAME,
    port=ZEROCONF_PORT,
    properties={"rp": ZEROCONF_RP},
)
