"""DHCP discovery data."""

from dataclasses import dataclass

from homeassistant.data_entry_flow import BaseServiceInfo


@dataclass(slots=True)
class DhcpServiceInfo(BaseServiceInfo):
    """Prepared info from dhcp entries."""

    ip: str
    hostname: str
    macaddress: str
    """The MAC address of the device.

    Please note that for historical reason the DHCP service will always format it
    as a lowercase string without colons.
    eg. "AA:BB:CC:12:34:56" is stored as "aabbcc123456"
    """
