"""Network utilities."""
from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
import re

import yarl

# RFC6890 - IP addresses of loopback interfaces
LOOPBACK_NETWORKS = (
    ip_network("127.0.0.0/8"),
    ip_network("::1/128"),
    ip_network("::ffff:127.0.0.0/104"),
)

# RFC6890 - Address allocation for Private Internets
PRIVATE_NETWORKS = (
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
    ip_network("fd00::/8"),
    ip_network("::ffff:10.0.0.0/104"),
    ip_network("::ffff:172.16.0.0/108"),
    ip_network("::ffff:192.168.0.0/112"),
)

# RFC6890 - Link local ranges
LINK_LOCAL_NETWORKS = (
    ip_network("169.254.0.0/16"),
    ip_network("fe80::/10"),
    ip_network("::ffff:169.254.0.0/112"),
)


def is_loopback(address: IPv4Address | IPv6Address) -> bool:
    """Check if an address is a loopback address."""
    return any(address in network for network in LOOPBACK_NETWORKS)


def is_private(address: IPv4Address | IPv6Address) -> bool:
    """Check if an address is a unique local non-loopback address."""
    return any(address in network for network in PRIVATE_NETWORKS)


def is_link_local(address: IPv4Address | IPv6Address) -> bool:
    """Check if an address is link-local (local but not necessarily unique)."""
    return any(address in network for network in LINK_LOCAL_NETWORKS)


def is_local(address: IPv4Address | IPv6Address) -> bool:
    """Check if an address is on a local network."""
    return is_loopback(address) or is_private(address) or is_link_local(address)


def is_invalid(address: IPv4Address | IPv6Address) -> bool:
    """Check if an address is invalid."""
    return bool(address == ip_address("0.0.0.0"))


def is_ip_address(address: str) -> bool:
    """Check if a given string is an IP address."""
    try:
        ip_address(address)
    except ValueError:
        return False

    return True


def is_ipv4_address(address: str) -> bool:
    """Check if a given string is an IPv4 address."""
    try:
        IPv4Address(address)
    except ValueError:
        return False

    return True


def is_ipv6_address(address: str) -> bool:
    """Check if a given string is an IPv6 address."""
    try:
        IPv6Address(address)
    except ValueError:
        return False

    return True


def is_host_valid(host: str) -> bool:
    """Check if a given string is an IP address or valid hostname."""
    if is_ip_address(host):
        return True
    if len(host) > 255:
        return False
    if re.match(r"^[0-9\.]+$", host):  # reject invalid IPv4
        return False
    if host.endswith("."):  # dot at the end is correct
        host = host[:-1]
    allowed = re.compile(r"(?!-)[A-Z\d\-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in host.split("."))


def normalize_url(address: str) -> str:
    """Normalize a given URL."""
    url = yarl.URL(address.rstrip("/"))
    if url.is_absolute() and url.is_default_port():
        return str(url.with_port(None))
    return str(url)
