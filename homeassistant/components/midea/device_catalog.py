"""Helpers for Midea device names and entity definitions."""

from midealocal.const import DeviceType

MIDEA_DEVICE_NAMES: dict[DeviceType, str] = {
    DeviceType.AC: "Air Conditioner",
    DeviceType.C3: "Heat Pump Wi-Fi Controller",
    DeviceType.CC: "MDV Wi-Fi Controller",
    DeviceType.CF: "Heat Pump",
    DeviceType.FB: "Electric Heater",
    DeviceType.X34: "Sink Dishwasher",
    DeviceType.A1: "Dehumidifier",
    DeviceType.C2: "Toilet",
    DeviceType.CE: "Fresh Air Appliance",
    DeviceType.E1: "Dishwasher",
    DeviceType.ED: "Water Drinking Appliance",
    DeviceType.FA: "Fan",
    DeviceType.FC: "Air Purifier",
}
