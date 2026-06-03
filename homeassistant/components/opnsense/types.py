"""Types for OPNsense routers."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from aiopnsense import OPNsenseClient

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import OPNsenseDeviceTrackerCoordinator


@dataclass(slots=True)
class OPNsenseRuntimeData:
    """Runtime data for OPNsense config entries."""

    client: OPNsenseClient
    tracker_interfaces: list[str]
    coordinator: OPNsenseDeviceTrackerCoordinator


type DeviceDetails = dict[str, Any]
type DeviceDetailsByMAC = dict[str, DeviceDetails]
type OPNsenseConfigEntry = ConfigEntry[OPNsenseRuntimeData]
