"""DHCP discovery data."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.data_entry_flow import BaseServiceInfo


@dataclass(slots=True)
class SsdpServiceInfo(BaseServiceInfo):
    """Prepared info from ssdp/upnp entries."""

    ssdp_usn: str
    ssdp_st: str
    upnp: Mapping[str, Any]
    ssdp_location: str | None = None
    ssdp_nt: str | None = None
    ssdp_udn: str | None = None
    ssdp_ext: str | None = None
    ssdp_server: str | None = None
    ssdp_headers: Mapping[str, Any] = field(default_factory=dict)
    ssdp_all_locations: set[str] = field(default_factory=set)
    x_homeassistant_matching_domains: set[str] = field(default_factory=set)
