"""Network utilities."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
import re

import yarl


def is_loopback(address: IPv4Address | IPv6Address) -> bool:
    """Check if an address is a loopback address."""
    # the ::ffff: check is a workaround for python/cpython#117566
    return address.is_loopback or address in ip_network("::ffff:127.0.0.0/104")


def is_private(address: IPv4Address | IPv6Address) -> bool:
    """Check if an address is a unique local non-loopback address."""
    return address.is_private and not is_loopback(address) and not address.is_link_local


def is_link_local(address: IPv4Address | IPv6Address) -> bool:
    """Check if an address is link-local (local but not necessarily unique)."""
    return address.is_link_local


def is_local(address: IPv4Address | IPv6Address) -> bool:
    """Check if an address is on a local network."""
    return is_loopback(address) or is_private(address) or is_link_local(address)


def is_invalid(address: IPv4Address | IPv6Address) -> bool:
    """Check if an address is invalid."""
    return address.is_unspecified


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
    host = host.removesuffix(".")
    allowed = re.compile(r"(?!-)[A-Z\d\-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in host.split("."))


def normalize_url(address: str) -> str:
    """Normalize a given URL."""
    url = yarl.URL(address.rstrip("/"))
    if url.is_absolute() and url.is_default_port():
        return str(url.with_port(None))
    return str(url)
