"""Helpers for Midea device names and entity definitions."""

from __future__ import annotations

from midealocal.const import DeviceType

MIDEA_DEVICE_NAMES: dict[DeviceType, str] = {
    DeviceType.X13: "Light",
    DeviceType.X26: "Bathroom Master",
    DeviceType.X34: "Sink Dishwasher",
    DeviceType.X40: "Integrated Ceiling Fan",
    DeviceType.A1: "Dehumidifier",
    DeviceType.AC: "Air Conditioner",
    DeviceType.AD: "Air Detector",
    DeviceType.B0: "Microwave Oven",
    DeviceType.B1: "Electric Oven",
    DeviceType.B3: "Dish Sterilizer",
    DeviceType.B4: "Toaster",
    DeviceType.B6: "Range Hood",
    DeviceType.BF: "Microwave Steam Oven",
    DeviceType.C2: "Toilet",
    DeviceType.C3: "Heat Pump Wi-Fi Controller",
    DeviceType.CA: "Refrigerator",
    DeviceType.CC: "MDV Wi-Fi Controller",
    DeviceType.CD: "Heat Pump Water Heater",
    DeviceType.CE: "Fresh Air Appliance",
    DeviceType.CF: "Heat Pump",
    DeviceType.DA: "Top Load Washer",
    DeviceType.DB: "Front Load Washer",
    DeviceType.DC: "Clothes Dryer",
    DeviceType.E1: "Dishwasher",
    DeviceType.E2: "Electric Water Heater",
    DeviceType.E3: "Gas Water Heater",
    DeviceType.E6: "Gas Boilers",
    DeviceType.E8: "Electric Slow Cooker",
    DeviceType.EA: "Electric Rice Cooker",
    DeviceType.EC: "Electric Pressure Cooker",
    DeviceType.ED: "Water Drinking Appliance",
    DeviceType.FA: "Fan",
    DeviceType.FB: "Electric Heater",
    DeviceType.FC: "Air Purifier",
    DeviceType.FD: "Humidifier",
}
