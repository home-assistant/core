"""Types for OPNsense routers."""

type DeviceDetails = dict[str, str | int | bool]
type DeviceDetailsByMAC = dict[str, DeviceDetails]
