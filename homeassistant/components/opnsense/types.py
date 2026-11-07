"""Types for OPNsense routers."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from aiopnsense import OPNsenseClient

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import (
        OPNsenseDeviceTrackerCoordinator,
        OPNsenseFirmwareCoordinator,
    )


@dataclass(slots=True)
class OPNsenseRuntimeData:
    """Runtime data for OPNsense config entries."""

    client: OPNsenseClient
    tracker_interfaces: list[str]
    update_coordinator: OPNsenseFirmwareCoordinator | None = None
    firmware_privilege_missing: bool = False
    tracked_devices: set[str] = field(default_factory=set)
    tracker_coordinator: OPNsenseDeviceTrackerCoordinator | None = None


type DeviceDetails = dict[str, Any]
type DeviceDetailsByMAC = dict[str, DeviceDetails]
type OPNsenseConfigEntry = ConfigEntry[OPNsenseRuntimeData]
