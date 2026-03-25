"""Zeroconf discovery data."""

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address
from typing import Any, Final

from homeassistant.data_entry_flow import BaseServiceInfo

# Attributes for ZeroconfServiceInfo[ATTR_PROPERTIES]
ATTR_PROPERTIES_ID: Final = "id"


@dataclass(slots=True)
class ZeroconfServiceInfo(BaseServiceInfo):
    """Prepared info from mDNS entries.

    The ip_address is the most recently updated address
    that is not a link local or unspecified address.

    The ip_addresses are all addresses in order of most
    recently updated to least recently updated.

    The host is the string representation of the ip_address.

    The addresses are the string representations of the
    ip_addresses.

    It is recommended to use the ip_address to determine
    the address to connect to as it will be the most
    recently updated address that is not a link local
    or unspecified address.
    """

    ip_address: IPv4Address | IPv6Address
    ip_addresses: list[IPv4Address | IPv6Address]
    port: int | None
    hostname: str
    type: str
    name: str
    properties: dict[str, Any]

    @property
    def host(self) -> str:
        """Return the host."""
        return str(self.ip_address)

    @property
    def addresses(self) -> list[str]:
        """Return the addresses."""
        return [str(ip_address) for ip_address in self.ip_addresses]
