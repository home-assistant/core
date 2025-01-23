"""Constants for Hunter Douglas Powerview tests."""

from ipaddress import IPv4Address

from homeassistant import config_entries
from homeassistant.components import dhcp, zeroconf

MOCK_MAC = "AA::BB::CC::DD::EE::FF"
MOCK_SERIAL = "A1B2C3D4E5G6H7"

HOMEKIT_DISCOVERY_GEN2 = zeroconf.ZeroconfServiceInfo(
    ip_address="1.2.3.4",
    ip_addresses=[IPv4Address("1.2.3.4")],
    hostname="mock_hostname",
    name="Powerview Generation 2._hap._tcp.local.",
    port=None,
    properties={zeroconf.ATTR_PROPERTIES_ID: MOCK_MAC},
    type="mock_type",
)

HOMEKIT_DISCOVERY_GEN3 = zeroconf.ZeroconfServiceInfo(
    ip_address="1.2.3.4",
    ip_addresses=[IPv4Address("1.2.3.4")],
    hostname="mock_hostname",
    name="Powerview Generation 3._hap._tcp.local.",
    port=None,
    properties={zeroconf.ATTR_PROPERTIES_ID: MOCK_MAC},
    type="mock_type",
)

ZEROCONF_DISCOVERY_GEN2 = zeroconf.ZeroconfServiceInfo(
    ip_address="1.2.3.4",
    ip_addresses=[IPv4Address("1.2.3.4")],
    hostname="mock_hostname",
    name="Powerview Generation 2._powerview._tcp.local.",
    port=None,
    properties={},
    type="mock_type",
)

ZEROCONF_DISCOVERY_GEN3 = zeroconf.ZeroconfServiceInfo(
    ip_address="1.2.3.4",
    ip_addresses=[IPv4Address("1.2.3.4")],
    hostname="mock_hostname",
    name="Powerview Generation 3._PowerView-G3._tcp.local.",
    port=None,
    properties={},
    type="mock_type",
)

DHCP_DISCOVERY_GEN2 = dhcp.DhcpServiceInfo(
    hostname="Powerview Generation 2",
    ip="1.2.3.4",
    macaddress="aabbccddeeff",
)

DHCP_DISCOVERY_GEN2_NO_NAME = dhcp.DhcpServiceInfo(
    hostname="",
    ip="1.2.3.4",
    macaddress="aabbccddeeff",
)

DHCP_DISCOVERY_GEN3 = dhcp.DhcpServiceInfo(
    hostname="Powerview Generation 3",
    ip="1.2.3.4",
    macaddress="aabbccddeeff",
)

HOMEKIT_DATA = [
    (
        config_entries.SOURCE_HOMEKIT,
        HOMEKIT_DISCOVERY_GEN2,
        2,
    ),
    (
        config_entries.SOURCE_HOMEKIT,
        HOMEKIT_DISCOVERY_GEN3,
        3,
    ),
]
DHCP_DATA = [
    (
        config_entries.SOURCE_DHCP,
        DHCP_DISCOVERY_GEN2,
        2,
    ),
    (
        config_entries.SOURCE_DHCP,
        DHCP_DISCOVERY_GEN3,
        3,
    ),
    (
        config_entries.SOURCE_DHCP,
        DHCP_DISCOVERY_GEN2_NO_NAME,
        2,
    ),
]
ZEROCONF_DATA = [
    (
        config_entries.SOURCE_ZEROCONF,
        ZEROCONF_DISCOVERY_GEN2,
        2,
    ),
    (
        config_entries.SOURCE_ZEROCONF,
        ZEROCONF_DISCOVERY_GEN3,
        3,
    ),
]
DISCOVERY_DATA = HOMEKIT_DATA + DHCP_DATA + ZEROCONF_DATA
