"""Models helper class for the network integration."""
from __future__ import annotations

from typing import TypedDict


class IPv6ConfiguredAddress(TypedDict):
    """Represent an IPv6 address."""

    address: str
    flowinfo: int
    scope_id: int
    network_prefix: int


class IPv4ConfiguredAddress(TypedDict):
    """Represent an IPv4 address."""

    address: str
    network_prefix: int


class Adapter(TypedDict):
    """Configured network adapters."""

    name: str
    index: int | None
    enabled: bool
    auto: bool
    default: bool
    ipv6: list[IPv6ConfiguredAddress]
    ipv4: list[IPv4ConfiguredAddress]
