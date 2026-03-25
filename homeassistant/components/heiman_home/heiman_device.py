"""Heiman Device abstraction.

Handles device property mapping and entity creation.
Integrates with heiman_device_mapping.py for property metadata.
"""

from __future__ import annotations

from importlib import import_module
import json
import logging
from typing import TYPE_CHECKING

from .heiman_coordinator import get_coordinator

if TYPE_CHECKING:
    from .binary_sensor import HeimanBinarySensorEntity
    from .button import HeimanButtonEntity
    from .cover import HeimanCoverEntity
    from .device_tracker import HeimanDeviceTrackerEntity
    from .event import HeimanEventEntity
    from .fan import HeimanFanEntity
    from .humidifier import HeimanHumidifierEntity
    from .light import HeimanLightEntity
    from .media_player import HeimanMediaPlayerEntity, HeimanNotifyEntity
    from .number import HeimanNumberEntity
    from .select import HeimanSelectEntity
    from .sensor import HeimanActivitySensor, HeimanSensorEntity
    from .switch import HeimanSwitchEntity
    from .text import HeimanTextEntity

_LOGGER = logging.getLogger(__name__)

# Import device mapping
try:
    from .heiman_device_mapping import get_product_properties, get_property_metadata

    HAS_MAPPING = True
    _LOGGER.debug("Successfully imported heiman_device_mapping")
except ImportError as import_err:
    _LOGGER.warning(
        "heiman_device_mapping not available, using basic mapping: %s",
        import_err,
    )
    HAS_MAPPING = False
except Exception as err:  # noqa: BLE001
    _LOGGER.warning(
        "Error importing heiman_device_mapping: %s, using basic mapping",
        err,
    )
    HAS_MAPPING = False

# Device property mapping - maps Heiman device properties to HA entities
# This should be customized based on actual device specifications
DEVICE_PROPERTY_MAPPING = {
    # Temperature sensor
    "temperature": {
        "type": "sensor",
        "name": "Temperature",
        "unit": "°C",
        "device_class": "temperature",
    },
    # Humidity sensor
    "humidity": {
        "type": "sensor",
        "name": "Humidity",
        "unit": "%",
        "device_class": "humidity",
    },
    # Smoke detector
    "smoke_status": {
        "type": "binary_sensor",
        "name": "Smoke",
        "device_class": "smoke",
    },
    # Motion sensor
    "motion_status": {
        "type": "binary_sensor",
        "name": "Motion",
        "device_class": "motion",
    },
    # Door/window sensor
    "door_status": {
        "type": "binary_sensor",
        "name": "Door",
        "device_class": "door",
    },
    # Water leak sensor
    "water_leak": {
        "type": "binary_sensor",
        "name": "Water Leak",
        "device_class": "moisture",
    },
    # CO sensor
    "co_status": {
        "type": "binary_sensor",
        "name": "CO",
        "device_class": "gas",
    },
    # Switch
    "switch_status": {
        "type": "switch",
        "name": "Switch",
    },
    # Power switch
    "power_switch": {
        "type": "switch",
        "name": "Power",
    },
    # Battery level
    "battery": {
        "type": "sensor",
        "name": "Battery",
        "unit": "%",
        "device_class": "battery",
    },
    # Signal strength
    "rssi": {
        "type": "sensor",
        "name": "Signal",
        "unit": "dBm",
        "device_class": "signal_strength",
    },
}


def _get_platform_entity(module_name: str, class_name: str):
    """Load an entity class without using inline import statements."""
    return getattr(import_module(f".{module_name}", __package__), class_name)


class HeimanDevice:
    """Represents a Heiman device and its entities."""

    def __init__(
        self,
        hass,
        device_info: dict,
        cloud_client,
        entry_id: str,
        i18n=None,
    ) -> None:
        """Initialize the device."""
        self._hass = hass
        self._device_info = device_info
        self._cloud_client = cloud_client
        self._entry_id = entry_id
        self._i18n = i18n

        # API returns 'id' field for device ID, but we also support 'deviceId' for compatibility
        self._device_id = device_info.get("id") or device_info.get("deviceId", "")
        self._product_id = device_info.get("productId", "")

        # Get device model from various possible fields
        # Priority: modelName > model > productName
        raw_model = (
            device_info.get("modelName")
            or device_info.get("model")
            or device_info.get("productName", "")
        )

        # Remove frequency suffixes like (915MHz) or (868MHz) from model name
        self._device_model = raw_model
        for freq in ["(915MHz)", "(868MHz)", "（868MHz）"]:
            if freq in raw_model:
                self._device_model = raw_model.replace(freq, "").strip()
                break

        # Get device name from various possible fields
        # Priority: deviceName > name > productName
        self._device_name = (
            device_info.get("deviceName")
            or device_info.get("name")
            or device_info.get("productName", "Unknown Device")
        )

        _LOGGER.info(
            "HeimanDevice initialized: device_id=%s, name=%s, model=%s, product_id=%s",
            self._device_id,
            self._device_name,
            self._device_model,
            self._product_id,
        )

        # Device properties will be parsed on-demand via async_init_properties()
        self._properties = []
        self._properties_initialized = False
        self._firmware_version = None

    @property
    def firmware_version(self) -> str | None:
        """Return the firmware version of the device."""
        return self._firmware_version

    async def async_init_properties(self) -> None:
        """Initialize device properties asynchronously.

        This should be called after HeimanDevice initialization to load properties.
        """
        if self._properties_initialized:
            return

        self._properties = await self._parse_device_properties()
        self._properties_initialized = True
        _LOGGER.debug(
            "Properties initialized for device %s: %d properties",
            self._device_id,
            len(self._properties),
        )

        # Log property type distribution
        self._log_property_distribution(self._properties)

    async def _parse_device_properties(self) -> list[dict]:  # noqa: C901
        """Parse device properties based on device model/product name."""
        properties = []

        # Try to fetch device detail from API first
        if self._cloud_client and hasattr(
            self._cloud_client,
            "async_get_device_instance_detail",
        ):
            try:
                _LOGGER.debug(
                    "Fetching device detail from API for device %s (%s)",
                    self._device_id,
                    self._device_name,
                )

                # Call /api-saas/device-instance/{device_id}/detail
                detail_result = (
                    await self._cloud_client.async_get_device_instance_detail(
                        self._device_id,
                    )
                )

                if detail_result:
                    # Extract firmware version from firmwareInfo if available
                    firmware_info = detail_result.get("firmwareInfo", {})
                    if isinstance(firmware_info, dict) and "version" in firmware_info:
                        # Store firmware version for sw_version matching
                        self._firmware_version = firmware_info.get("version")
                        _LOGGER.debug(
                            "Extracted firmware version %s for device %s from device instance API firmwareInfo",
                            self._firmware_version,
                            self._device_id,
                        )

                    # Parse metadata JSON string
                    _LOGGER.debug(
                        "Got device detail from API for device %s: %s",
                        self._device_id,
                        detail_result,
                    )
                    metadata_str = detail_result.get("metadata", "")
                    if metadata_str:
                        try:
                            metadata = json.loads(metadata_str)

                            # Extract properties from metadata
                            properties_list = metadata.get("properties", [])
                            if isinstance(properties_list, list):
                                _LOGGER.debug(
                                    "Found %d properties from API for device %s",
                                    len(properties_list),
                                    self._device_id,
                                )

                                # Convert property definitions to entity format
                                # Reference: xiaomi_home specv2entity.py logic
                                for prop_def in properties_list:
                                    prop_id = prop_def.get("id", "")
                                    if not prop_id:
                                        continue

                                    prop_name = prop_def.get("name", prop_id)
                                    value_type = prop_def.get("valueType", {})
                                    expands = prop_def.get("expands", {})

                                    # Parse access types from expands.type array
                                    # type: ["read", "write", "report"]
                                    # - read: readable
                                    # - write: writable
                                    # - report: supports push/report
                                    access_types = expands.get("type", [])
                                    is_writable = "write" in access_types

                                    # Determine property type based on valueType and access
                                    # Priority logic:
                                    # 1. If NOT writable (no 'write' in access), default to 'sensor'
                                    # 2. If writable, determine type based on vt_type
                                    prop_type = "sensor"  # Default
                                    device_class = None
                                    unit = None
                                    icon = None

                                    vt_type = value_type.get("type", "")
                                    elements = value_type.get("elements", [])

                                    # Rule 1: If not writable, treat as sensor (read-only)
                                    if not is_writable:
                                        # Read-only properties are sensors
                                        prop_type = "sensor"

                                        # Special handling for bool type (read-only = binary_sensor)
                                        if vt_type == "bool":
                                            prop_type = "binary_sensor"
                                        # Special handling for enum type (read-only = sensor or binary_sensor)
                                        elif (
                                            vt_type == "enum"
                                            and elements
                                            and isinstance(elements, list)
                                        ):
                                            [str(e.get("value", "")) for e in elements]
                                            # Enum with 2 states (0/1) = binary_sensor

                                    # Rule 2: If writable, determine type based on vt_type
                                    # Check bool type first (writable bool = switch)
                                    elif vt_type == "bool" or (
                                        vt_type == "enum"
                                        and elements
                                        and isinstance(elements, list)
                                    ):
                                        prop_type = "switch"
                                    # Numeric types remain as sensor (can be writable for control)
                                    elif vt_type in [
                                        "int",
                                        "double",
                                        "float",
                                        "long",
                                        "short",
                                        "byte",
                                        "number",
                                    ]:
                                        prop_type = "sensor"
                                    # String, date, array, object, file types become text sensors
                                    elif vt_type in ["string", "date"]:
                                        prop_type = "sensor"  # Will be handled as non-numeric sensor
                                    elif vt_type in ["array", "object", "file"]:
                                        prop_type = "sensor"  # Complex types will be converted to JSON strings
                                    elif vt_type == "date":
                                        device_class = "timestamp"

                                    # Add unit and device_class for numeric sensors
                                    if prop_type == "sensor" and vt_type in [
                                        "int",
                                        "double",
                                        "float",
                                        "long",
                                        "short",
                                        "byte",
                                        "number",
                                    ]:
                                        unit = value_type.get("unit")
                                        if prop_id == "RSSI":
                                            device_class = "signal_strength"
                                            unit = "dBm"
                                        elif prop_id == "BatteryPercentage":
                                            device_class = "battery"
                                            unit = "%"
                                        elif prop_id in [
                                            "CurrentTemperature",
                                            "temperature",
                                        ]:
                                            device_class = "temperature"
                                            unit = "°C"
                                        elif prop_id in ["CurrentHumidity", "humidity"]:
                                            device_class = "humidity"
                                            unit = "%"

                                    # Button identification logic - more flexible than hardcoded IDs
                                    if prop_id in [
                                        "RemoteLocate",
                                        "Mute",
                                        "RemoteCheck",
                                    ]:
                                        prop_type = "button"
                                    elif prop_id == "AlarmSoundOption":
                                        prop_type = "select"

                                    # 特殊处理一些产品字段 网关
                                    if self._product_id in [
                                        "2034958781083516928",
                                        "2018250377056022528",
                                        "2001581958272577536",
                                        "1976552577824727040",
                                        "1960251398905970688",
                                        "1960250096146759680",
                                        "1932322027567980544",
                                        "1901601085789986816",
                                        "1870278823705071616",
                                        "1810843560026951680",
                                        "1733421468953686016",
                                        "1712723441528012800",
                                        "1712402758738575360",
                                        "1712401376535052288",
                                        "1712400967301005312",
                                        "1712360385354596352",
                                        "1712007899645149184",
                                    ]:
                                        if prop_id in [
                                            "AlarmSoundOption",
                                            "LightSwitch",
                                            "TimeZone",
                                            "DeviceINFO",
                                        ]:
                                            if prop_id == "AlarmSoundOption":
                                                prop_type = "select"
                                                device_class = "sound"
                                                icon = "mdi:volume-high"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "AlarmSoundOption.name",
                                                        "Sound Option",
                                                    )
                                                    if self._i18n
                                                    else "Sound Option"
                                                )
                                            elif prop_id == "LightSwitch":
                                                prop_type = "switch"
                                                device_class = "switch"
                                                icon = "mdi:lightbulb-outline"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "LightSwitch.name",
                                                        "Indicator Light Switch",
                                                    )
                                                    if self._i18n
                                                    else "Indicator Light Switch"
                                                )
                                            elif prop_id == "TimeZone":
                                                icon = "mdi:clock-time-nine-outline"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "TimeZone.name",
                                                        "Device Time Zone",
                                                    )
                                                    if self._i18n
                                                    else "Device Time Zone"
                                                )
                                            elif prop_id == "DeviceINFO":
                                                # Create MAC address sensor
                                                properties.append(
                                                    {
                                                        "id": "DeviceINFO_MAC",
                                                        "name": self._i18n.translate(
                                                            "property",
                                                            "DeviceINFO_MAC.name",
                                                            "MAC Address",
                                                        )
                                                        if self._i18n
                                                        else "MAC Address",
                                                        "type": "sensor",
                                                        "device_class": None,
                                                        "icon": "mdi:dharmachakra",
                                                        "parent_property": "DeviceINFO",
                                                        "json_field": "MAC",
                                                    },
                                                )
                                                # Create signal strength sensor
                                                properties.append(
                                                    {
                                                        "id": "DeviceINFO_DBM",
                                                        "name": self._i18n.translate(
                                                            "property",
                                                            "DeviceINFO_DBM.name",
                                                            "Signal Strength",
                                                        )
                                                        if self._i18n
                                                        else "Signal Strength",
                                                        "type": "sensor",
                                                        "device_class": "signal_strength",
                                                        "unit": "dBm",
                                                        "icon": "mdi:signal",
                                                        "parent_property": "DeviceINFO",
                                                        "json_field": "DBM",
                                                    },
                                                )
                                                # Create signal strength level sensor (similar to RSSI_Level)
                                                properties.append(
                                                    {
                                                        "id": "DeviceINFO_DBM_Level",
                                                        "name": self._i18n.translate(
                                                            "property",
                                                            "DeviceINFO_DBM_Level.name",
                                                            "Signal Strength Level",
                                                        )
                                                        if self._i18n
                                                        else "Signal Strength Level",
                                                        "type": "sensor",
                                                        "device_class": "enum",
                                                        "icon": "mdi:signal",
                                                        "parent_property": "DeviceINFO",
                                                        "json_field": "DBM",
                                                        "options": [
                                                            self._i18n.translate(
                                                                "property",
                                                                "DeviceINFO_DBM_Level.options.strong",
                                                                "Strong",
                                                            )
                                                            if self._i18n
                                                            else "Strong",
                                                            self._i18n.translate(
                                                                "property",
                                                                "DeviceINFO_DBM_Level.options.medium",
                                                                "Medium",
                                                            )
                                                            if self._i18n
                                                            else "Medium",
                                                            self._i18n.translate(
                                                                "property",
                                                                "DeviceINFO_DBM_Level.options.weak",
                                                                "Weak",
                                                            )
                                                            if self._i18n
                                                            else "Weak",
                                                            self._i18n.translate(
                                                                "property",
                                                                "DeviceINFO_DBM_Level.options.very_weak",
                                                                "Very Weak",
                                                            )
                                                            if self._i18n
                                                            else "Very Weak",
                                                        ],
                                                    },
                                                )
                                                # Create IP address sensor
                                                properties.append(
                                                    {
                                                        "id": "DeviceINFO_IP",
                                                        "name": self._i18n.translate(
                                                            "property",
                                                            "DeviceINFO_IP.name",
                                                            "IP Address",
                                                        )
                                                        if self._i18n
                                                        else "IP Address",
                                                        "type": "sensor",
                                                        "device_class": None,
                                                        "icon": "mdi:ip",
                                                        "parent_property": "DeviceINFO",
                                                        "json_field": "IP",
                                                    },
                                                )
                                                continue
                                        else:
                                            continue
                                    # Special handling for smoke sensor products
                                    if self._product_id in [
                                        "2029440661815095296",
                                        "2029438274199154688",
                                        "2013145744913657856",
                                        "2007989417262379008",
                                        "1991745959373635584",
                                        "1986705377032818688",
                                        "1985528410954682368",
                                        "1985526736966012928",
                                        "1981621464757325824",
                                        "1968114912378396672",
                                        "1905532161226346496",
                                        "1901600411274600448",
                                        "1825452011297071104",
                                        "1810857540850143232",
                                        "1734821218500292608",
                                    ]:
                                        # Check if DeviceMac already exists to avoid duplicates
                                        existing_prop_ids = [
                                            p.get("id") for p in properties
                                        ]
                                        if "DeviceMac" not in existing_prop_ids:
                                            properties.append(
                                                {
                                                    "id": "DeviceMac",
                                                    "name": self._i18n.translate(
                                                        "property",
                                                        "DeviceMac.name",
                                                        "MAC Address",
                                                    )
                                                    if self._i18n
                                                    else "MAC Address",
                                                    "type": "sensor",
                                                    "device_class": None,
                                                    "icon": "mdi:dharmachakra",
                                                    "json_field": "name",
                                                },
                                            )
                                        if prop_id in [
                                            "RemoteLocate",
                                            "RemoteCheck",
                                            "Mute",
                                            "LightSwitch",
                                            "SmokeSensorState",
                                            "CurrentTemperature",
                                            "TamperState",
                                            "UnderVoltError",
                                            "BatteryPercentage",
                                        ]:
                                            if prop_id == "RemoteLocate":
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "RemoteLocate.name",
                                                        "Remote Locate",
                                                    )
                                                    if self._i18n
                                                    else "Remote Locate"
                                                )
                                            elif prop_id == "RemoteCheck":
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "RemoteCheck.name",
                                                        "Remote Check",
                                                    )
                                                    if self._i18n
                                                    else "Remote Check"
                                                )
                                            elif prop_id == "Mute":
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "Mute.name",
                                                        "Remote Mute",
                                                    )
                                                    if self._i18n
                                                    else "Remote Mute"
                                                )
                                            elif prop_id == "CurrentTemperature":
                                                prop_type = "sensor"
                                                device_class = "temperature"
                                                icon = "mdi:thermometer"
                                                unit = "°C"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "CurrentTemperature.name",
                                                        "Current Temperature",
                                                    )
                                                    if self._i18n
                                                    else "Current Temperature"
                                                )
                                            elif prop_id == "LightSwitch":
                                                prop_type = "switch"
                                                device_class = "switch"
                                                icon = "mdi:lightbulb-outline"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "LightSwitch.name",
                                                        "Indicator Light Switch",
                                                    )
                                                    if self._i18n
                                                    else "Indicator Light Switch"
                                                )
                                            elif prop_id == "SmokeSensorState":
                                                prop_type = "binary_sensor"
                                                device_class = "smoke"
                                                icon = "mdi:smoke"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "SmokeSensorState.name",
                                                        "Smoke Alarm Status",
                                                    )
                                                    if self._i18n
                                                    else "Smoke Alarm Status"
                                                )
                                            elif prop_id == "TamperState":
                                                prop_type = "binary_sensor"
                                                device_class = "tamper"
                                                icon = "mdi:alert"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "TamperState.name",
                                                        "Tamper Alert Status",
                                                    )
                                                    if self._i18n
                                                    else "Tamper Alert Status"
                                                )
                                            elif prop_id == "BatteryPercentage":
                                                prop_type = "sensor"
                                                device_class = "battery"
                                                icon = "mdi:battery"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "BatteryPercentage.name",
                                                        "Battery Percentage",
                                                    )
                                                    if self._i18n
                                                    else "Battery Percentage"
                                                )
                                            elif prop_id == "UnderVoltError":
                                                prop_type = "binary_sensor"
                                                device_class = "battery"
                                                icon = "mdi:battery-alert-variant"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "UnderVoltError.name",
                                                        "Low Battery Alert Status",
                                                    )
                                                    if self._i18n
                                                    else "Low Battery Alert Status"
                                                )
                                        else:
                                            continue
                                    # Special handling for water leak sensor products
                                    if self._product_id in [
                                        "2003374935470960640",
                                        "1925004014149328896",
                                        "1925003834175938560",
                                        "1712640220090007552",
                                        "1712366595122331648",
                                        "1902647452417347584",
                                        "1902647647511203840",
                                        "1712024520782708736",
                                    ]:
                                        # Check if DeviceMac already exists to avoid duplicates
                                        existing_prop_ids = [
                                            p.get("id") for p in properties
                                        ]
                                        if "DeviceMac" not in existing_prop_ids:
                                            properties.append(
                                                {
                                                    "id": "DeviceMac",
                                                    "name": self._i18n.translate(
                                                        "property",
                                                        "DeviceMac.name",
                                                        "MAC Address",
                                                    )
                                                    if self._i18n
                                                    else "MAC Address",
                                                    "type": "sensor",
                                                    "device_class": None,
                                                    "icon": "mdi:dharmachakra",
                                                    "json_field": "name",
                                                },
                                            )
                                        if prop_id in [
                                            "FreezingPointEnable",
                                            "BuzzerEnable",
                                            "Mute",
                                            "LightSwitch",
                                            "RemoteCheck",
                                            "WaterSensorState",
                                            "FreezingPointAlarm",
                                            "UnderVoltError",
                                            "BatteryPercentage",
                                        ]:
                                            if prop_id == "FreezingPointEnable":
                                                device_class = "sound"
                                                icon = "mdi:snowflake-alert"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "FreezingPointEnable.name",
                                                        "Freezing Point Alarm Enable",
                                                    )
                                                    if self._i18n
                                                    else "Freezing Point Alarm Enable"
                                                )
                                            elif prop_id == "BuzzerEnable":
                                                icon = "mdi:surround-sound"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "BuzzerEnable.name",
                                                        "Alarm Sound Switch",
                                                    )
                                                    if self._i18n
                                                    else "Alarm Sound Switch"
                                                )
                                            elif prop_id == "Mute":
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "Mute.name",
                                                        "Remote Mute",
                                                    )
                                                    if self._i18n
                                                    else "Remote Mute"
                                                )
                                            elif prop_id == "RemoteCheck":
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "RemoteCheck.name",
                                                        "Remote Check",
                                                    )
                                                    if self._i18n
                                                    else "Remote Check"
                                                )
                                            elif prop_id == "LightSwitch":
                                                prop_type = "switch"
                                                device_class = "switch"
                                                icon = "mdi:lightbulb-outline"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "LightSwitch.name",
                                                        "Indicator Light Switch",
                                                    )
                                                    if self._i18n
                                                    else "Indicator Light Switch"
                                                )
                                            elif prop_id == "WaterSensorState":
                                                prop_type = "binary_sensor"
                                                device_class = "moisture"
                                                icon = "mdi:water"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "WaterSensorState.name",
                                                        "Water Leak Alarm Status",
                                                    )
                                                    if self._i18n
                                                    else "Water Leak Alarm Status"
                                                )
                                            elif prop_id == "FreezingPointAlarm":
                                                prop_type = "binary_sensor"
                                                device_class = "cold"
                                                icon = "mdi:water-thermometer-outline"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "FreezingPointAlarm.name",
                                                        "Freezing Point Alarm Status",
                                                    )
                                                    if self._i18n
                                                    else "Freezing Point Alarm Status"
                                                )
                                            elif prop_id == "BatteryPercentage":
                                                prop_type = "sensor"
                                                device_class = "battery"
                                                icon = "mdi:battery"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "BatteryPercentage.name",
                                                        "Battery Percentage",
                                                    )
                                                    if self._i18n
                                                    else "Battery Percentage"
                                                )
                                            elif prop_id == "UnderVoltError":
                                                prop_type = "binary_sensor"
                                                device_class = "battery"
                                                icon = "mdi:battery-alert-variant"
                                                prop_name = (
                                                    self._i18n.translate(
                                                        "property",
                                                        "UnderVoltError.name",
                                                        "Low Battery Alert Status",
                                                    )
                                                    if self._i18n
                                                    else "Low Battery Alert Status"
                                                )
                                        else:
                                            continue

                                    # Build property info dict
                                    prop_info = {
                                        "id": prop_id,
                                        "name": prop_name,
                                        "type": prop_type,
                                        "device_class": device_class,
                                        "icon": icon,
                                    }

                                    # Add options and value mappings for AlarmSoundOption
                                    if prop_id == "AlarmSoundOption":
                                        # Translate alarm sound options
                                        fast_beep = (
                                            self._i18n.translate(
                                                "property",
                                                "AlarmSoundOption.options.fast",
                                                "Fast Beep",
                                            )
                                            if self._i18n
                                            else "Fast Beep"
                                        )
                                        medium_beep = (
                                            self._i18n.translate(
                                                "property",
                                                "AlarmSoundOption.options.medium",
                                                "Medium Beep",
                                            )
                                            if self._i18n
                                            else "Medium Beep"
                                        )
                                        slow_beep = (
                                            self._i18n.translate(
                                                "property",
                                                "AlarmSoundOption.options.slow",
                                                "Slow Beep",
                                            )
                                            if self._i18n
                                            else "Slow Beep"
                                        )

                                        alarm_options = [
                                            fast_beep,
                                            medium_beep,
                                            slow_beep,
                                        ]
                                        prop_info["options"] = alarm_options
                                        prop_info["value_list"] = {
                                            fast_beep: "0",
                                            medium_beep: "1",
                                            slow_beep: "2",
                                        }
                                        # Also add reverse mapping for select.py
                                        prop_info["reverse_value_list"] = {
                                            "0": fast_beep,
                                            "1": medium_beep,
                                            "2": slow_beep,
                                        }

                                    # Only add unit if it's set and applicable (not for binary_sensor/switch/select)
                                    if unit is not None and prop_type not in [
                                        "binary_sensor",
                                        "switch",
                                        "select",
                                    ]:
                                        prop_info["unit"] = unit
                                    properties.append(prop_info)

                            _LOGGER.info(
                                "Successfully parsed properties from device instance API for %s: %s",
                                self._device_id,
                                properties,
                            )

                            # Log property types for debugging
                            prop_types = {}
                            for prop in properties:
                                prop_type = prop.get("type", "unknown")
                                prop_types[prop_type] = prop_types.get(prop_type, 0) + 1
                            _LOGGER.info(
                                "Property type distribution for %s: %s",
                                self._device_id,
                                prop_types,
                            )

                        except json.JSONDecodeError as err:
                            _LOGGER.warning(
                                "Failed to parse metadata JSON for device %s: %s",
                                self._device_id,
                                err,
                            )
                            # Fallback to basic mapping below
                        except Exception as err:  # noqa: BLE001
                            _LOGGER.warning(
                                "Error parsing device detail metadata for device %s: %s",
                                self._device_id,
                                err,
                                exc_info=True,
                            )
                            # Fallback to basic mapping below
                    else:
                        _LOGGER.debug(
                            "No metadata field in device detail response for %s",
                            self._device_id,
                        )
                        # Fallback to basic mapping below
                else:
                    _LOGGER.debug(
                        "Empty device detail response for %s, using basic mapping",
                        self._device_id,
                    )
                    # Fallback to basic mapping below

            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to fetch device detail from API for %s: %s, using basic mapping",
                    self._device_id,
                    err,
                )
                # Fallback to basic mapping below

        # If no properties fetched from API, use basic mapping
        if not properties:
            properties = self._parse_device_properties_basic()
        else:
            # Properties fetched from API, add common properties that may not be in metadata
            # Check if BatteryPercentage already exists
            prop_ids = [p.get("id") for p in properties]
            # if 'RSSI' not in prop_ids:
            #     properties.append({
            #         'id': 'RSSI',
            #         **DEVICE_PROPERTY_MAPPING.get('rssi', {})
            #     })

            # Add RSSI signal strength level as sensor entity (not select)
            # This provides a user-friendly view of signal quality (Strong/Medium/Weak/Very Weak)
            # Using sensor instead of select because it's a read-only status, not user-selectable
            if "DeviceINFO_DBM" not in prop_ids:
                if "RSSI_Level" not in prop_ids:
                    # Translate RSSI level name and options
                    rssi_level_name = (
                        self._i18n.translate(
                            "property",
                            "RSSI_Level.name",
                            "Signal Strength Level",
                        )
                        if self._i18n
                        else "Signal Strength Level"
                    )
                    strong = (
                        self._i18n.translate(
                            "property",
                            "RSSI_Level.options.strong",
                            "Strong",
                        )
                        if self._i18n
                        else "Strong"
                    )
                    medium = (
                        self._i18n.translate(
                            "property",
                            "RSSI_Level.options.medium",
                            "Medium",
                        )
                        if self._i18n
                        else "Medium"
                    )
                    weak = (
                        self._i18n.translate(
                            "property",
                            "RSSI_Level.options.weak",
                            "Weak",
                        )
                        if self._i18n
                        else "Weak"
                    )
                    very_weak = (
                        self._i18n.translate(
                            "property",
                            "RSSI_Level.options.very_weak",
                            "Very Weak",
                        )
                        if self._i18n
                        else "Very Weak"
                    )

                    properties.append(
                        {
                            "id": "RSSI_Level",
                            "name": rssi_level_name,
                            "type": "sensor",
                            "device_class": "enum",
                            "icon": "mdi:signal",
                            "options": [strong, medium, weak, very_weak],
                            # No unit needed - this is an enum showing signal level text
                        },
                    )

        # Sort properties by ID according to predefined order
        # properties = self._sort_properties_by_id(properties)

        return properties

    def _log_property_distribution(self, properties: list[dict]) -> None:
        """Log the distribution of property types."""
        prop_types = {}
        for prop in properties:
            prop_type = prop.get("type", "unknown")
            prop_types[prop_type] = prop_types.get(prop_type, 0) + 1
        _LOGGER.info("Final property type distribution: %s", prop_types)

    def _sort_properties_by_id(self, properties: list[dict]) -> list[dict]:
        """Sort properties by ID according to predefined order.

        Sorting order: AlarmSoundOption, FreezingPointEnable, BuzzerEnable, RemoteLocate,
        RemoteCheck, Mute, LightSwitch, TimeZone, DeviceINFO_MAC, DeviceINFO_DBM,
        DeviceINFO_IP, SmokeSensorState, CurrentTemperature, TamperState,
        WaterSensorState, FreezingPointAlarm, UnderVoltError, BatteryPercentage,
        RSSI_Level, DeviceMac

        Properties not in the predefined order are appended at the end.
        """
        # Define the desired order
        property_order = [
            "AlarmSoundOption",
            "FreezingPointEnable",
            "BuzzerEnable",
            "RemoteLocate",
            "RemoteCheck",
            "Mute",
            "LightSwitch",
            "TimeZone",
            "DeviceINFO_MAC",
            "DeviceINFO_DBM",
            "DeviceINFO_IP",
            "SmokeSensorState",
            "CurrentTemperature",
            "TamperState",
            "WaterSensorState",
            "FreezingPointAlarm",
            "UnderVoltError",
            "BatteryPercentage",
            "RSSI_Level",
            "DeviceMac",
        ]

        # Create a mapping of property ID to its index in the order list
        order_map = {prop_id: idx for idx, prop_id in enumerate(property_order)}

        # Sort properties: those in order_map first (by their index), then others (by ID)
        def sort_key(prop):
            prop_id = prop.get("id", "")
            if prop_id in order_map:
                return (0, order_map[prop_id])
            return (1, prop_id)

        sorted_properties = sorted(properties, key=sort_key)

        _LOGGER.debug(
            "Properties sorted for device %s: order = %s",
            self._device_id,
            [p.get("id") for p in sorted_properties],
        )

        return sorted_properties

    def _parse_device_properties_basic(self) -> list[dict]:
        """Parse device properties based on device model/product name."""
        # Use new mapping if available
        if HAS_MAPPING:
            try:
                # Try to get properties using product name first (most reliable)
                # Priority: modelName > productName > device_name
                product_name_for_lookup = (
                    self._device_info.get("modelName")
                    or self._device_info.get("productName")
                    or self._device_name
                )

                product_properties = get_product_properties(product_name_for_lookup)
                if product_properties:
                    _LOGGER.debug(
                        "Found %s properties for device '%s' (matched as '%s') using product name mapping",
                        len(product_properties),
                        self._device_name,
                        product_name_for_lookup,
                    )

                    # Convert property IDs to entity format
                    properties = []
                    for prop_id in product_properties:
                        metadata = get_property_metadata(prop_id)
                        if metadata:
                            prop_info = {
                                "id": prop_id,
                                "name": metadata.get("name", prop_id),
                                "type": metadata.get("platform", "sensor"),
                                "device_class": metadata.get("device_class"),
                                "unit": metadata.get("unit_of_measurement"),
                                "icon": metadata.get("icon"),
                            }
                            properties.append(prop_info)
                        else:
                            # Fallback for unmapped properties
                            properties.append(
                                {
                                    "id": prop_id,
                                    "name": prop_id,
                                    "type": "sensor",
                                },
                            )

                    return properties
                _LOGGER.debug(
                    "No property mapping found for product: %s (lookup: %s, model: %s)",
                    self._device_name,
                    product_name_for_lookup,
                    self._device_model,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Error using new device mapping: %s, falling back to basic mapping",
                    err,
                )

        # Fallback to basic mapping
        properties = []
        model_lower = self._device_model.lower()
        name_lower = self._device_name.lower()

        _LOGGER.info(
            "Using basic property mapping for: %s (model: %s, name: %s)",
            self._device_id,
            self._device_model,
            self._device_name,
        )

        # Try to detect device type from model or name
        if any(
            keyword in model_lower or keyword in name_lower
            for keyword in ["temp", "temperature", "温", "th"]
        ):
            properties.append(
                {
                    "id": "CurrentTemperature",
                    **DEVICE_PROPERTY_MAPPING.get("temperature", {}),
                },
            )

        if any(
            keyword in model_lower or keyword in name_lower
            for keyword in ["hum", "humidity", "湿度", "ht"]
        ):
            properties.append(
                {
                    "id": "CurrentHumidity",
                    **DEVICE_PROPERTY_MAPPING.get("humidity", {}),
                },
            )

        if any(
            keyword in model_lower or keyword in name_lower
            for keyword in ["smoke", "烟雾", "s1", "fs"]
        ):
            properties.append(
                {
                    "id": "SmokeSensorState",
                    **DEVICE_PROPERTY_MAPPING.get("smoke_status", {}),
                },
            )

        if any(
            keyword in model_lower or keyword in name_lower
            for keyword in ["motion", "pir", "红外", "ms"]
        ):
            properties.append(
                {
                    "id": "MotionAlarmState",
                    **DEVICE_PROPERTY_MAPPING.get("motion_status", {}),
                },
            )

        if any(
            keyword in model_lower or keyword in name_lower
            for keyword in ["door", "window", "magnetic", "门磁", "ds"]
        ):
            properties.append(
                {
                    "id": "ContactState",
                    **DEVICE_PROPERTY_MAPPING.get("door_status", {}),
                },
            )

        if any(
            keyword in model_lower or keyword in name_lower
            for keyword in ["water", "leak", "水浸", "wl"]
        ):
            properties.append(
                {
                    "id": "WaterSensorState",
                    **DEVICE_PROPERTY_MAPPING.get("water_leak", {}),
                },
            )

        if any(
            keyword in model_lower or keyword in name_lower
            for keyword in ["co", "carbon", "一氧化碳", "gas"]
        ):
            properties.append(
                {
                    "id": "GasSensorState",
                    **DEVICE_PROPERTY_MAPPING.get("co_status", {}),
                },
            )

        if any(
            keyword in model_lower or keyword in name_lower
            for keyword in ["heat", "温感", "hw"]
        ):
            properties.append(
                {
                    "id": "HeatSensorStatus",
                    "type": "binary_sensor",
                    "name": "Heat Alarm",
                    "device_class": "heat",
                },
            )

        if any(
            keyword in model_lower or keyword in name_lower
            for keyword in ["switch", "开关", "sw", "light", "灯"]
        ):
            properties.append(
                {
                    "id": "LightSwitch",
                    **DEVICE_PROPERTY_MAPPING.get("switch_status", {}),
                },
            )

        # Note: Common properties (BatteryPercentage, RSSI, StateTime, Version)
        # are added in _parse_device_properties() to avoid duplication

        _LOGGER.info("Generated %s properties using basic mapping", len(properties))
        return properties

    def get_sensor_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanSensorEntity]:
        """Get sensor entities for this device."""
        sensor_entity = _get_platform_entity("sensor", "HeimanSensorEntity")
        entities = []
        coordinator = get_coordinator(self._hass, self._entry_id)

        # 收集所有传感器属性名称用于批量获取
        sensor_property_names = []

        for prop in self._properties:
            if prop.get("type") == "sensor":
                entities.append(
                    sensor_entity(
                        coordinator=coordinator,
                        device_info=self.device_info,  # Use property instead of instance variable
                        property_info=prop,
                        cloud_client=self._cloud_client,
                        i18n=self._i18n,
                        devices_config=devices_config,
                    ),
                )
                sensor_property_names.append(prop.get("id"))

        # 注册属性名称到 coordinator，用于批量获取
        if sensor_property_names and coordinator:
            coordinator.register_device_properties(
                self._device_id,
                sensor_property_names,
            )

        return entities

    def get_binary_sensor_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanBinarySensorEntity]:
        """Get binary sensor entities for this device."""
        binary_sensor_entity = _get_platform_entity(
            "binary_sensor",
            "HeimanBinarySensorEntity",
        )
        entities = []
        coordinator = get_coordinator(self._hass, self._entry_id)

        # 收集所有二进制传感器属性名称用于批量获取
        binary_sensor_property_names = []

        for prop in self._properties:
            if prop.get("type") == "binary_sensor":
                entities.append(
                    binary_sensor_entity(
                        coordinator=coordinator,
                        device_info=self.device_info,  # Use property instead of instance variable
                        property_info=prop,
                        cloud_client=self._cloud_client,
                        device_class=prop.get("device_class"),
                        devices_config=devices_config,
                    ),
                )
                binary_sensor_property_names.append(prop.get("id"))

        # 注册属性名称到 coordinator，用于批量获取
        if binary_sensor_property_names and coordinator:
            coordinator.register_device_properties(
                self._device_id,
                binary_sensor_property_names,
            )

        return entities

    def get_switch_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanSwitchEntity]:
        """Get switch entities for this device."""
        switch_entity = _get_platform_entity("switch", "HeimanSwitchEntity")
        entities = []
        coordinator = get_coordinator(self._hass, self._entry_id)

        # 收集所有开关属性名称用于批量获取
        switch_property_names = []

        for prop in self._properties:
            if prop.get("type") == "switch":
                entities.append(
                    switch_entity(
                        coordinator=coordinator,
                        device_info=self.device_info,  # Use property instead of instance variable
                        property_info=prop,
                        cloud_client=self._cloud_client,
                        devices_config=devices_config,
                    ),
                )
                switch_property_names.append(prop.get("id"))

        # 注册属性名称到 coordinator，用于批量获取
        if switch_property_names and coordinator:
            coordinator.register_device_properties(
                self._device_id,
                switch_property_names,
            )

        return entities

    def get_activity_sensor(
        self,
        devices_config: dict | None = None,
        max_alarms: int = 10,
    ) -> HeimanActivitySensor | None:
        """Get activity sensor for this device.

        Args:
            devices_config: Device configuration overrides
            max_alarms: Maximum number of alarms to fetch

        Returns:
            HeimanActivitySensor instance or None
        """
        activity_sensor = _get_platform_entity("sensor", "HeimanActivitySensor")
        return activity_sensor(
            coordinator=get_coordinator(self._hass, self._entry_id),
            device_info=self.device_info,  # Use property instead of instance variable
            cloud_client=self._cloud_client,
            i18n=self._i18n,
            devices_config=devices_config,
            max_alarms=max_alarms,
        )

    def get_button_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanButtonEntity]:
        """Get button entities for this device."""
        button_entity = _get_platform_entity("button", "HeimanButtonEntity")
        coordinator = get_coordinator(self._hass, self._entry_id)
        return [
            button_entity(
                coordinator=coordinator,
                device_info=self.device_info,
                property_info=prop,
                cloud_client=self._cloud_client,
                i18n=self._i18n,
                devices_config=devices_config,
            )
            for prop in self._properties
            if prop.get("type") == "button"
        ]

    def get_cover_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanCoverEntity]:
        """Get cover entities for this device."""
        cover_entity = _get_platform_entity("cover", "HeimanCoverEntity")
        coordinator = get_coordinator(self._hass, self._entry_id)
        return [
            cover_entity(
                coordinator=coordinator,
                device_info=self.device_info,
                property_info=prop,
                cloud_client=self._cloud_client,
                i18n=self._i18n,
                devices_config=devices_config,
            )
            for prop in self._properties
            if prop.get("type") == "cover"
        ]

    def get_fan_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanFanEntity]:
        """Get fan entities for this device."""
        fan_entity = _get_platform_entity("fan", "HeimanFanEntity")
        coordinator = get_coordinator(self._hass, self._entry_id)
        return [
            fan_entity(
                coordinator=coordinator,
                device_info=self.device_info,
                property_info=prop,
                cloud_client=self._cloud_client,
                i18n=self._i18n,
                devices_config=devices_config,
            )
            for prop in self._properties
            if prop.get("type") == "fan"
        ]

    def get_light_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanLightEntity]:
        """Get light entities for this device."""
        light_entity = _get_platform_entity("light", "HeimanLightEntity")
        coordinator = get_coordinator(self._hass, self._entry_id)
        return [
            light_entity(
                coordinator=coordinator,
                device_info=self.device_info,
                property_info=prop,
                cloud_client=self._cloud_client,
                i18n=self._i18n,
                devices_config=devices_config,
            )
            for prop in self._properties
            if prop.get("type") == "light"
        ]

    def get_humidifier_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanHumidifierEntity]:
        """Get humidifier entities for this device."""
        humidifier_entity = _get_platform_entity(
            "humidifier",
            "HeimanHumidifierEntity",
        )
        coordinator = get_coordinator(self._hass, self._entry_id)
        return [
            humidifier_entity(
                coordinator=coordinator,
                device_info=self.device_info,
                property_info=prop,
                cloud_client=self._cloud_client,
                i18n=self._i18n,
                devices_config=devices_config,
            )
            for prop in self._properties
            if prop.get("type") == "humidifier"
        ]

    def get_number_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanNumberEntity]:
        """Get number entities for this device."""
        number_entity = _get_platform_entity("number", "HeimanNumberEntity")
        coordinator = get_coordinator(self._hass, self._entry_id)
        return [
            number_entity(
                coordinator=coordinator,
                device_info=self.device_info,
                property_info=prop,
                cloud_client=self._cloud_client,
                i18n=self._i18n,
                devices_config=devices_config,
            )
            for prop in self._properties
            if prop.get("type") == "number"
        ]

    def get_select_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanSelectEntity]:
        """Get select entities for this device."""
        select_entity = _get_platform_entity("select", "HeimanSelectEntity")
        coordinator = get_coordinator(self._hass, self._entry_id)
        return [
            select_entity(
                coordinator=coordinator,
                device_info=self.device_info,
                property_info=prop,
                cloud_client=self._cloud_client,
                i18n=self._i18n,
                devices_config=devices_config,
            )
            for prop in self._properties
            if prop.get("type") == "select"
        ]

    def get_event_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanEventEntity]:
        """Get event entities for this device."""
        event_entity = _get_platform_entity("event", "HeimanEventEntity")
        coordinator = get_coordinator(self._hass, self._entry_id)
        return [
            event_entity(
                coordinator=coordinator,
                device_info=self.device_info,
                property_info=prop,
                cloud_client=self._cloud_client,
                i18n=self._i18n,
                devices_config=devices_config,
            )
            for prop in self._properties
            if prop.get("type") == "event"
        ]

    def get_text_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanTextEntity]:
        """Get text entities for this device."""
        text_entity = _get_platform_entity("text", "HeimanTextEntity")
        coordinator = get_coordinator(self._hass, self._entry_id)
        return [
            text_entity(
                coordinator=coordinator,
                device_info=self.device_info,
                property_info=prop,
                cloud_client=self._cloud_client,
                i18n=self._i18n,
                devices_config=devices_config,
            )
            for prop in self._properties
            if prop.get("type") == "text"
        ]

    def get_device_tracker_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanDeviceTrackerEntity]:
        """Get device tracker entities for this device."""
        device_tracker_entity = _get_platform_entity(
            "device_tracker",
            "HeimanDeviceTrackerEntity",
        )
        coordinator = get_coordinator(self._hass, self._entry_id)
        return [
            device_tracker_entity(
                coordinator=coordinator,
                device_info=self.device_info,
                property_info=prop,
                cloud_client=self._cloud_client,
                i18n=self._i18n,
                devices_config=devices_config,
            )
            for prop in self._properties
            if prop.get("type") == "device_tracker"
        ]

    def get_media_player_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanMediaPlayerEntity]:
        """Get media player entities for this device."""
        media_player_entity = _get_platform_entity(
            "media_player",
            "HeimanMediaPlayerEntity",
        )
        coordinator = get_coordinator(self._hass, self._entry_id)
        return [
            media_player_entity(
                coordinator=coordinator,
                device_info=self.device_info,
                property_info=prop,
                cloud_client=self._cloud_client,
                i18n=self._i18n,
                devices_config=devices_config,
            )
            for prop in self._properties
            if prop.get("type") == "media_player"
        ]

    def get_notify_entities(
        self,
        devices_config: dict | None = None,
    ) -> list[HeimanNotifyEntity]:
        """Get notify entities for this device."""
        notify_entity = _get_platform_entity("media_player", "HeimanNotifyEntity")
        coordinator = get_coordinator(self._hass, self._entry_id)
        return [
            notify_entity(
                coordinator=coordinator,
                device_info=self.device_info,
                property_info=prop,
                cloud_client=self._cloud_client,
                i18n=self._i18n,
                devices_config=devices_config,
            )
            for prop in self._properties
            if prop.get("type") == "notify"
        ]

    @property
    def device_id(self) -> str:
        """Get the device ID."""
        return self._device_id

    @property
    def product_id(self) -> str:
        """Get the product ID."""
        return self._product_id

    @property
    def device_info(self) -> dict:
        """Get the device info."""
        # Create a copy to avoid modifying the original
        device_info = dict(self._device_info)

        # Add firmware version if available
        if self._firmware_version:
            device_info["sw_version"] = self._firmware_version
            _LOGGER.debug(
                "device_info property returning firmware version %s for device %s",
                self._firmware_version,
                self._device_id,
            )

        return device_info
