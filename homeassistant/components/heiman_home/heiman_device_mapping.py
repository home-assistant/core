"""Heiman Device Property Mapping.

Maps Heiman device properties (from物模型) to Home Assistant entities.
This file contains the complete property mapping for all supported devices.
"""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


# Property type to HA platform mapping
PROPERTY_TYPE_TO_PLATFORM = {
    "int": "sensor",
    "float": "sensor",
    "double": "sensor",
    "string": "sensor",
    "enum": "binary_sensor",
    "bool": "binary_sensor",
    "date": "sensor",
}


# Property ID to HA device class and unit mapping
PROPERTY_METADATA: dict[str, dict[str, Any]] = {
    # Temperature properties
    "CurrentTemperature": {
        "name": "Temperature",
        "device_class": "temperature",
        "unit_of_measurement": "°C",
        "state_class": "measurement",
        "platform": "sensor",
        "icon": "mdi:thermometer",
    },
    "TempHighThreshold": {
        "name": "High Temperature Threshold",
        "device_class": "temperature",
        "unit_of_measurement": "°C",
        "platform": "sensor",
        "icon": "mdi:thermometer-chevron-up",
    },
    "TempLowThreshold": {
        "name": "Low Temperature Threshold",
        "device_class": "temperature",
        "unit_of_measurement": "°C",
        "platform": "sensor",
        "icon": "mdi:thermometer-chevron-down",
    },
    # Humidity properties
    "CurrentHumidity": {
        "name": "Humidity",
        "device_class": "humidity",
        "unit_of_measurement": "%",
        "state_class": "measurement",
        "platform": "sensor",
        "icon": "mdi:water-percent",
    },
    "HumidityHighThreshold": {
        "name": "High Humidity Threshold",
        "device_class": "humidity",
        "unit_of_measurement": "%",
        "platform": "sensor",
        "icon": "mdi:water-percent",
    },
    "HumidityLowThreshold": {
        "name": "Low Humidity Threshold",
        "device_class": "humidity",
        "unit_of_measurement": "%",
        "platform": "sensor",
        "icon": "mdi:water-percent",
    },
    # Sensor properties
    "SmokeSensorState": {
        "name": "Smoke",
        "device_class": "smoke",
        "platform": "binary_sensor",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:smoke-detector",
    },
    "GasSensorState": {
        "name": "CO",
        "device_class": "gas",
        "platform": "binary_sensor",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:gas-cylinder",
    },
    "HeatSensorStatus": {
        "name": "Heat Alarm",
        "device_class": "heat",
        "platform": "binary_sensor",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:fire-alert",
    },
    "MotionAlarmState": {
        "name": "Motion",
        "device_class": "motion",
        "platform": "binary_sensor",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:motion-sensor",
    },
    "WaterSensorState": {
        "name": "Water Leak",
        "device_class": "moisture",
        "platform": "binary_sensor",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:water-alert",
    },
    "ContactState": {
        "name": "Door/Window",
        "device_class": "door",
        "platform": "binary_sensor",
        "on_value": 1,  # Open
        "off_value": 0,  # Closed
        "icon": "mdi:door-open",
    },
    "SwitchState": {
        "name": "Alarm State",
        "device_class": "safety",
        "platform": "binary_sensor",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:shield-alert",
    },
    # Battery and signal
    "BatteryPercentage": {
        "name": "Battery",
        "device_class": "battery",
        "unit_of_measurement": "%",
        "state_class": "measurement",
        "platform": "sensor",
        "icon": "mdi:battery",
    },
    "RSSI": {
        "name": "Signal Strength",
        "device_class": "signal_strength",
        "unit_of_measurement": "dBm",
        "state_class": "measurement",
        "platform": "sensor",
        "icon": "mdi:wifi-strength-outline",
    },
    # Alarm and fault states
    "UnderVoltError": {
        "name": "Low Battery",
        "device_class": "battery",
        "platform": "binary_sensor",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:battery-alert",
    },
    "Fault": {
        "name": "Fault",
        "device_class": "problem",
        "platform": "binary_sensor",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:alert-circle",
    },
    "TamperState": {
        "name": "Tamper",
        "device_class": "tamper",
        "platform": "binary_sensor",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:shield-remove",
    },
    # Control properties (switches)
    "ArmModeControl": {
        "name": "Arm Mode",
        "platform": "switch",
        "property_id": "ArmModeControl",
        "on_value": 1,  # Armed
        "off_value": 0,  # Disarmed
        "icon": "mdi:shield-home",
    },
    "LightSwitch": {
        "name": "LED",
        "platform": "switch",
        "property_id": "LightSwitch",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:led-outline",
    },
    "Mute": {
        "name": "Mute",
        "platform": "switch",
        "property_id": "Mute",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:volume-off",
    },
    "RemoteCheck": {
        "name": "Self-Test",
        "platform": "switch",
        "property_id": "RemoteCheck",
        "on_value": 1,
        "off_value": 0,
        "momentary": True,  # Self-test is momentary
        "icon": "mdi:test-tube",
    },
    "RemoteLocate": {
        "name": "Locate",
        "platform": "switch",
        "property_id": "RemoteLocate",
        "on_value": 1,
        "off_value": 0,
        "momentary": True,  # Locate is momentary
        "icon": "mdi:map-marker-radius",
    },
    "BuzzerEnable": {
        "name": "Buzzer",
        "platform": "switch",
        "property_id": "BuzzerEnable",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:bullhorn",
    },
    "FreezingPointEnable": {
        "name": "Freeze Alarm",
        "platform": "switch",
        "property_id": "FreezingPointEnable",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:snowflake-alert",
    },
    "TempEnable": {
        "name": "Temp Alarm Enable",
        "platform": "switch",
        "property_id": "TempEnable",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:thermometer-alert",
    },
    "HumidityEnable": {
        "name": "Humidity Alarm Enable",
        "platform": "switch",
        "property_id": "HumidityEnable",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:water-percent-alert",
    },
    "PowerSavingMode": {
        "name": "Power Saving",
        "platform": "switch",
        "property_id": "PowerSavingMode",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:leaf",
    },
    # Settings (number/select sensors)
    "SensitivitySettings": {
        "name": "Sensitivity",
        "platform": "select",
        "property_id": "SensitivitySettings",
        "options": ["0", "1", "2"],  # High, Medium, Low
        "options_map": {
            "0": "High",
            "1": "Medium",
            "2": "Low",
        },
        "icon": "mdi:tune",
    },
    "DT": {
        "name": "Delay Time",
        "platform": "select",
        "property_id": "DT",
        "options": ["60", "120", "180", "300", "600"],
        "options_map": {
            "60": "1 min",
            "120": "2 min",
            "180": "3 min",
            "300": "5 min",
            "600": "10 min",
        },
        "icon": "mdi:timer-outline",
    },
    "SwitchTimeout": {
        "name": "Door Timeout",
        "platform": "select",
        "property_id": "SwitchTimeout",
        "options": ["1", "2", "3", "4", "5", "6", "7", "8"],
        "options_map": {
            "1": "1 min",
            "2": "2 min",
            "3": "3 min",
            "4": "5 min",
            "5": "10 min",
            "6": "15 min",
            "7": "20 min",
            "8": "30 min",
        },
        "icon": "mdi:door-closed-lock",
    },
    "TUI": {
        "name": "Temp Unit",
        "platform": "select",
        "property_id": "TUI",
        "options": ["0", "1"],
        "options_map": {
            "0": "°C",
            "1": "°F",
        },
        "icon": "mdi:temperature-celsius",
    },
    # Sensor values (read-only sensors)
    "CONC": {
        "name": "CO Concentration",
        "device_class": None,
        "unit_of_measurement": "ppm",
        "platform": "sensor",
        "icon": "mdi:gas-cylinder",
    },
    "Version": {
        "name": "Firmware",
        "device_class": None,
        "platform": "sensor",
        "icon": "mdi:chip",
    },
    "CertifiedVersion": {
        "name": "Certified Version",
        "device_class": None,
        "platform": "sensor",
        "icon": "mdi:certificate",
    },
    "DeviceINFO": {
        "name": "Device Info",
        "device_class": None,
        "platform": "sensor",
        "icon": "mdi:information",
    },
    "SetTime": {
        "name": "Set Time",
        "device_class": None,
        "platform": "sensor",
        "icon": "mdi:clock-edit",
    },
    "TimeZone": {
        "name": "Time Zone",
        "device_class": None,
        "platform": "sensor",
        "icon": "mdi:earth",
    },
    "UserName": {
        "name": "User Name",
        "device_class": None,
        "platform": "sensor",
        "icon": "mdi:account",
    },
    "SetCMD": {
        "name": "Command",
        "device_class": None,
        "platform": "sensor",
        "icon": "mdi:command-palette",
    },
    "MasterDevice": {
        "name": "Master Device",
        "device_class": None,
        "platform": "sensor",
        "icon": "mdi:router-network",
    },
    "RestTimes": {
        "name": "Rest Times",
        "device_class": None,
        "platform": "sensor",
        "icon": "mdi:timer-outline",
    },
    "Index": {
        "name": "Index",
        "device_class": None,
        "platform": "sensor",
        "icon": "mdi:numeric",
    },
    "StateTime": {
        "name": "Last Update",
        "device_class": "timestamp",
        "platform": "sensor",
        "icon": "mdi:clock-outline",
    },
    "GatewayMac": {
        "name": "Gateway",
        "device_class": None,
        "platform": "sensor",
        "icon": "mdi:router-wireless",
    },
    # Alarm type sensors
    "TempAlarmType": {
        "name": "Temp Alarm Type",
        "platform": "sensor",
        "options_map": {
            "0": "Normal",
            "1": "High",
            "2": "Low",
        },
        "icon": "mdi:thermometer-alert",
    },
    "HumiAlarmType": {
        "name": "Humidity Alarm Type",
        "platform": "sensor",
        "options_map": {
            "0": "Normal",
            "1": "High",
            "2": "Low",
        },
        "icon": "mdi:water-percent-alert",
    },
    "TempShowType": {
        "name": "Temp Comfort",
        "platform": "binary_sensor",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:thermometer-lines",
    },
    "HumidityShowType": {
        "name": "Humidity Comfort",
        "platform": "binary_sensor",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:water-check",
    },
    # Threshold settings (number sensors)
    "TempHighComfort": {
        "name": "Temp High Comfort",
        "device_class": "temperature",
        "unit_of_measurement": "°C",
        "platform": "number",
        "icon": "mdi:thermometer-high",
    },
    "TempLowComfort": {
        "name": "Temp Low Comfort",
        "device_class": "temperature",
        "unit_of_measurement": "°C",
        "platform": "number",
        "icon": "mdi:thermometer-low",
    },
    "HumidityHighComfort": {
        "name": "Humidity High Comfort",
        "device_class": "humidity",
        "unit_of_measurement": "%",
        "platform": "number",
        "icon": "mdi:water-percent",
    },
    "HumidityLowComfort": {
        "name": "Humidity Low Comfort",
        "device_class": "humidity",
        "unit_of_measurement": "%",
        "platform": "number",
        "icon": "mdi:water-percent",
    },
    "FreezingPointAlarm": {
        "name": "Freeze Alarm",
        "device_class": "cold",
        "platform": "binary_sensor",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:snowflake-alert",
    },
    "SwitchTimeoutEnable": {
        "name": "Door Timeout Enable",
        "platform": "switch",
        "property_id": "SwitchTimeoutEnable",
        "on_value": 1,
        "off_value": 0,
        "icon": "mdi:door-closed-lock",
    },
}


# Product name to property mapping
# Maps product names (from device info) to supported properties
PRODUCT_PROPERTY_MAPPING: dict[str, list[str]] = {
    # Smoke Alarm
    "烟雾报警器S1-R(915MHz)": [
        "SmokeSensorState",
        "BatteryPercentage",
        "RSSI",
        "UnderVoltError",
        "Fault",
        "TamperState",
        "LightSwitch",
        "Mute",
        "RemoteCheck",
        "RemoteLocate",
        "CurrentTemperature",
        "Version",
        "SetTime",
    ],
    # CO Alarm
    "一氧化碳报警器-HM-733ESY-W(868MHz)": [
        "GasSensorState",
        "BatteryPercentage",
        "RSSI",
        "UnderVoltError",
        "Fault",
        "LightSwitch",
        "Mute",
        "RemoteCheck",
        "RemoteLocate",
        "CONC",
        "Version",
        "SetTime",
    ],
    # Temperature/Humidity Sensor
    "温湿度探测器HS3HT-2R(868MHz)": [
        "CurrentTemperature",
        "CurrentHumidity",
        "BatteryPercentage",
        "RSSI",
        "UnderVoltError",
        "TempHighThreshold",
        "TempLowThreshold",
        "HumidityHighThreshold",
        "HumidityLowThreshold",
        "TempEnable",
        "HumidityEnable",
        "TUI",
        "TempAlarmType",
        "HumiAlarmType",
        "TempShowType",
        "HumidityShowType",
        "TempHighComfort",
        "TempLowComfort",
        "HumidityHighComfort",
        "HumidityLowComfort",
        "PowerSavingMode",
        "StateTime",
        "GatewayMac",
        "Index",
    ],
    # Motion Detector (PIR)
    "红外探测器HS1MS-R(868MHz)": [
        "MotionAlarmState",
        "ArmModeControl",
        "BatteryPercentage",
        "RSSI",
        "UnderVoltError",
        "TamperState",
        "SensitivitySettings",
        "DT",
        "StateTime",
        "GatewayMac",
        "Index",
    ],
    # Water Leak Detector
    "水浸探测器HS2WL-R(868MHz)": [
        "WaterSensorState",
        "BatteryPercentage",
        "RSSI",
        "UnderVoltError",
        "TamperState",
        "FreezingPointAlarm",
        "FreezingPointEnable",
        "BuzzerEnable",
        "LightSwitch",
        "Mute",
        "RemoteCheck",
        "StateTime",
        "GatewayMac",
        "Index",
    ],
    # Heat Alarm
    "温感报警器HM-5HW-T(868MHz)": [
        "HeatSensorStatus",
        "BatteryPercentage",
        "RSSI",
        "UnderVoltError",
        "Fault",
        "TamperState",
        "CurrentTemperature",
        "LightSwitch",
        "Mute",
        "RemoteCheck",
        "RemoteLocate",
        "Version",
        "StateTime",
        "GatewayMac",
        "Index",
    ],
    # Door/Window Sensor
    "门磁探测器HS1DS-R(868MHz)": [
        "ContactState",
        "ArmModeControl",
        "BatteryPercentage",
        "RSSI",
        "UnderVoltError",
        "TamperState",
        "SwitchTimeout",
        "SwitchTimeoutEnable",
        "LightSwitch",
        "StateTime",
        "GatewayMac",
        "Index",
    ],
    # Gateway
    "无线级联网关WS2GW-R（868MHz）": [
        "RSSI",
        "TimeZone",
        "UserName",
        "LightSwitch",
        "Mute",
        "SetCMD",
        "CertifiedVersion",
        "DeviceINFO",
        "MasterDevice",
        "RestTimes",
    ],
}


# Common properties for all devices
COMMON_PROPERTIES = [
    "BatteryPercentage",
    "RSSI",
    "StateTime",
    "Version",
]


def get_property_metadata(property_id: str) -> dict[str, Any] | None:
    """Get metadata for a property."""
    return PROPERTY_METADATA.get(property_id)


def get_product_properties(product_name: str) -> list[str]:
    """Get property IDs for a product."""
    # Try exact match first
    if product_name in PRODUCT_PROPERTY_MAPPING:
        return PRODUCT_PROPERTY_MAPPING[product_name]

    # Try partial match
    for product, properties in PRODUCT_PROPERTY_MAPPING.items():
        if product in product_name or product_name in product:
            _LOGGER.debug("Partial match: %s -> %s", product_name, product)
            return properties

    # Return common properties if no match
    _LOGGER.warning(
        "No property mapping found for product: %s, using common properties",
        product_name,
    )
    return COMMON_PROPERTIES


def map_property_to_entity(property_id: str, property_value: Any) -> Any:
    """Map property value to HA entity state."""
    metadata = get_property_metadata(property_id)

    if metadata is None:
        return property_value

    # For binary sensors with custom on/off values
    if metadata.get("platform") == "binary_sensor":
        on_value = metadata.get("on_value", 1)
        off_value = metadata.get("off_value", 0)

        if property_value == on_value:
            return True
        if property_value == off_value:
            return False
        # Try to convert to bool
        return bool(property_value)

    # For select sensors with options map
    if metadata.get("platform") == "select":
        options_map = metadata.get("options_map", {})
        return options_map.get(str(property_value), property_value)

    # For temperature/humidity sensors
    if metadata.get("device_class") in ["temperature", "humidity"]:
        try:
            return float(property_value)
        except ValueError, TypeError:
            return property_value

    # For switches with custom on/off values
    if metadata.get("platform") == "switch":
        on_value = metadata.get("on_value", 1)
        off_value = metadata.get("off_value", 0)
        return property_value in [on_value, True, 1]

    return property_value


def map_entity_to_property(property_id: str, entity_state: Any) -> Any:
    """Map HA entity state to property value."""
    metadata = get_property_metadata(property_id)

    if metadata is None:
        return entity_state

    # For binary sensors with custom on/off values
    if metadata.get("platform") == "binary_sensor":
        on_value = metadata.get("on_value", 1)
        off_value = metadata.get("off_value", 0)
        return on_value if entity_state else off_value

    # For select sensors with options map
    if metadata.get("platform") == "select":
        options_map = metadata.get("options_map", {})
        # Reverse lookup
        for value, label in options_map.items():
            if entity_state in (label, value):
                return value
        return entity_state

    # For switches with custom on/off values
    if metadata.get("platform") == "switch":
        on_value = metadata.get("on_value", 1)
        off_value = metadata.get("off_value", 0)
        return on_value if entity_state else off_value

    return entity_state
