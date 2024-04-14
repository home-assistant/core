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
    macaddress="9cadef000000",
)


class MockPyObihai:
    """Mock PyObihai: Returns simulated PyObihai data."""

    def get_device_mac(self):
        """Mock PyObihai.get_device_mac, return simulated MAC address."""

        return DHCP_SERVICE_INFO.macaddress


def get_schema_suggestion(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema:
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
