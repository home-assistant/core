"""Helpers for Midea device names and entity definitions."""

from midealocal.const import DeviceType

MIDEA_DEVICE_NAMES: dict[DeviceType, str] = {
    DeviceType.AC: "Air Conditioner",
    DeviceType.C3: "Heat Pump Wi-Fi Controller",
    DeviceType.CC: "MDV Wi-Fi Controller",
    DeviceType.CF: "Heat Pump",
    DeviceType.FB: "Electric Heater",
    DeviceType.X40: "Integrated Ceiling Fan",
    DeviceType.B6: "Range Hood",
    DeviceType.CE: "Fresh Air Appliance",
    DeviceType.FA: "Fan",
}
