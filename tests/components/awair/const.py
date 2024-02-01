"""Constants used in Awair tests."""

from ipaddress import ip_address

from homeassistant.components import zeroconf
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST

AWAIR_UUID = "awair_24947"
CLOUD_CONFIG = {CONF_ACCESS_TOKEN: "12345"}
LOCAL_CONFIG = {CONF_HOST: "192.0.2.5"}
CLOUD_UNIQUE_ID = "foo@bar.com"
LOCAL_UNIQUE_ID = "00:B0:D0:63:C2:26"
ZEROCONF_DISCOVERY = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("192.0.2.5"),
    ip_addresses=[ip_address("192.0.2.5")],
    hostname="mock_hostname",
    name="awair12345",
    port=None,
    type="_http._tcp.local.",
    properties={},
)
