"""Models helper class for the network integration."""
from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address
from typing import TypedDict


class IPv6ConfiguredAddress(TypedDict):
    """Represent an IPv6 address."""

    address: IPv6Address
    flowinfo: int
    scope_id: int
    network_prefix: int


class IPv4ConfiguredAddress(TypedDict):
    """Represent an IPv4 address."""

    address: IPv4Address
    network_prefix: int


class Adapter(TypedDict):
    """Configured network adapters."""

    name: str
    enabled: bool
    default: bool
    ipv6: list[IPv6ConfiguredAddress]
    ipv4: list[IPv4ConfiguredAddress]
