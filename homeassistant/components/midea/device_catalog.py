"""Helpers for Midea device names and entity definitions."""

from midealocal.const import DeviceType

MIDEA_DEVICE_NAMES: dict[DeviceType, str] = {
    DeviceType.A1: "Dehumidifier",
    DeviceType.AC: "Air Conditioner",
    DeviceType.B6: "Range Hood",
    DeviceType.C2: "Toilet",
    DeviceType.C3: "Heat Pump Wi-Fi Controller",
    DeviceType.CC: "MDV Wi-Fi Controller",
    DeviceType.CD: "Heat Pump Water Heater",
    DeviceType.CE: "Fresh Air Appliance",
    DeviceType.CF: "Heat Pump",
    DeviceType.E1: "Dishwasher",
    DeviceType.ED: "Water Drinking Appliance",
    DeviceType.FA: "Fan",
    DeviceType.FB: "Electric Heater",
    DeviceType.FC: "Air Purifier",
    DeviceType.FD: "Humidifier",
    DeviceType.X13: "Light",
    DeviceType.X26: "Bathroom Master",
    DeviceType.X40: "Integrated Ceiling Fan",
}
