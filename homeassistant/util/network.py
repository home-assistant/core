"""Network utilities."""
from ipaddress import IPv4Address, IPv6Address, ip_network
from typing import Union

# RFC6890 - IP addresses of loopback interfaces
LOOPBACK_NETWORKS = (
    ip_network("127.0.0.0/8"),
    ip_network("::1/128"),
    ip_network("::ffff:127.0.0.0/104"),
)

# RFC6890 - Address allocation for Private Internets
PRIVATE_NETWORKS = (
    ip_network("fd00::/8"),
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
)

# RFC6890 - Link local ranges
LINK_LOCAL_NETWORK = ip_network("169.254.0.0/16")


def is_loopback(address: Union[IPv4Address, IPv6Address]) -> bool:
    """Check if an address is a loopback address."""
    return any(address in network for network in LOOPBACK_NETWORKS)


def is_private(address: Union[IPv4Address, IPv6Address]) -> bool:
    """Check if an address is a private address."""
    return any(address in network for network in PRIVATE_NETWORKS)


def is_link_local(address: Union[IPv4Address, IPv6Address]) -> bool:
    """Check if an address is link local."""
    return address in LINK_LOCAL_NETWORK


def is_local(address: Union[IPv4Address, IPv6Address]) -> bool:
    """Check if an address is loopback or private."""
    return is_loopback(address) or is_private(address)
