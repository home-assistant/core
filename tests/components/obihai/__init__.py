"""Tests for the Obihai Integration."""

from homeassistant.components import dhcp
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

USER_INPUT = {
    CONF_HOST: "10.10.10.30",
    CONF_PASSWORD: "admin",
    CONF_USERNAME: "admin",
}

DHCP_SERVICE_INFO = dhcp.DhcpServiceInfo(
    hostname="obi200",
    ip="192.168.1.100",
    macaddress="9CADEF000000",
)
