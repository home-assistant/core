"""DHCP discovery data."""

from dataclasses import dataclass

from homeassistant.data_entry_flow import BaseServiceInfo


@dataclass(slots=True)
class DhcpServiceInfo(BaseServiceInfo):
    """Prepared info from dhcp entries."""

    ip: str
    hostname: str
    macaddress: str
