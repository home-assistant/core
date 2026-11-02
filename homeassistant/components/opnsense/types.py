"""Types for OPNsense routers."""

from dataclasses import dataclass, field
from typing import Any

from aiopnsense import OPNsenseClient

from homeassistant.config_entries import ConfigEntry


@dataclass(slots=True)
class OPNsenseRuntimeData:
    """Runtime data for OPNsense config entries."""

    client: OPNsenseClient
    tracker_interfaces: list[str]
    tracked_devices: set[str] = field(default_factory=set)


type DeviceDetails = dict[str, Any]
type DeviceDetailsByMAC = dict[str, DeviceDetails]
type OPNsenseConfigEntry = ConfigEntry[OPNsenseRuntimeData]
