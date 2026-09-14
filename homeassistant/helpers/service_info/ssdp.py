"""SSDP discovery data."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from homeassistant.data_entry_flow import BaseServiceInfo

# Attributes for accessing info from retrieved UPnP device description
ATTR_ST: Final = "st"
ATTR_NT: Final = "nt"
ATTR_UPNP_DEVICE_TYPE: Final = "deviceType"
ATTR_UPNP_FRIENDLY_NAME: Final = "friendlyName"
ATTR_UPNP_MANUFACTURER: Final = "manufacturer"
ATTR_UPNP_MANUFACTURER_URL: Final = "manufacturerURL"
ATTR_UPNP_MODEL_DESCRIPTION: Final = "modelDescription"
ATTR_UPNP_MODEL_NAME: Final = "modelName"
ATTR_UPNP_MODEL_NUMBER: Final = "modelNumber"
ATTR_UPNP_MODEL_URL: Final = "modelURL"
ATTR_UPNP_SERIAL: Final = "serialNumber"
ATTR_UPNP_SERVICE_LIST: Final = "serviceList"
ATTR_UPNP_UDN: Final = "UDN"
ATTR_UPNP_UPC: Final = "UPC"
ATTR_UPNP_PRESENTATION_URL: Final = "presentationURL"


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
