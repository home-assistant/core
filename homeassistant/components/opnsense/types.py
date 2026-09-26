"""Types for OPNsense routers."""

type DeviceDetails = dict[str, str | int | bool | None]
type DeviceDetailsByMAC = dict[str, DeviceDetails]
