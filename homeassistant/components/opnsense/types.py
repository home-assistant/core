"""Types for OPNsense routers."""

from typing import Any

type DeviceDetails = dict[str, Any]
type DeviceDetailsByMAC = dict[str, DeviceDetails]
