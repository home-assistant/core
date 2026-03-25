"""Sensor entities for Heiman Home Integration."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
import json
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .common import get_initialized_device
from .const import CONF_DEVICES_CONFIG, DEFAULT_INTEGRATION_LANGUAGE, DOMAIN
from .heiman_coordinator import get_coordinator
from .heiman_i18n import get_i18n

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heiman Home sensors."""
    entry_id = config_entry.entry_id
    devices_dict = hass.data[DOMAIN]["devices"].get(entry_id, {})

    _LOGGER.info("=" * 80)
    _LOGGER.info("Setting up Heiman Home sensors for entry: %s", entry_id)
    _LOGGER.info("=" * 80)

    # Convert devices dict to list if needed
    if isinstance(devices_dict, dict):
        devices = list(devices_dict.values())
    else:
        devices = devices_dict if isinstance(devices_dict, list) else []

    _LOGGER.info(
        "Total devices in hass.data[DOMAIN]['devices'][%s]: %s",
        entry_id,
        len(devices),
    )

    # Get language preference
    language = config_entry.options.get(
        "language",
        config_entry.data.get("language", DEFAULT_INTEGRATION_LANGUAGE),
    )
    i18n = get_i18n(language)

    devices_config = config_entry.data.get(CONF_DEVICES_CONFIG, {})

    # Get coordinator and cloud client
    coordinator = get_coordinator(hass, entry_id)
    cloud_client = hass.data[DOMAIN]["clients"][entry_id]

    entities = []

    for device in devices:
        device_id = device.get("id") or device.get("deviceId", "")
        device_name = (
            device.get("deviceName")
            or device.get("name")
            or device.get("productName", "Unknown")
        )
        device_model = (
            device.get("modelName")
            or device.get("model")
            or device.get("productName", "")
        )

        _LOGGER.debug(
            "Processing device: ID=%s, Name=%s, Model=%s",
            device_id,
            device_name,
            device_model,
        )

        # Reuse initialized device object from hass.data
        heiman_device = get_initialized_device(
            hass=hass,
            entry_id=entry_id,
            device_id=device_id,
            device_info=device,
            cloud_client=cloud_client,
            i18n=i18n,
        )

        # Add sensor entities based on device properties with device config
        sensor_entities = heiman_device.get_sensor_entities(
            devices_config=devices_config,
        )
        _LOGGER.debug(
            "  Device %s has %s sensor entities",
            device_name,
            len(sensor_entities),
        )
        entities.extend(sensor_entities)

        # Add activity sensor for each device
        activity_sensor = HeimanActivitySensor(
            coordinator=coordinator,
            device_info=device,
            cloud_client=cloud_client,
            i18n=i18n,
            devices_config=devices_config,
            max_alarms=10,
        )
        entities.append(activity_sensor)
        _LOGGER.debug("  Device %s has activity sensor", device_name)

    _LOGGER.info("Adding %s sensor entities for entry %s", len(entities), entry_id)

    if not entities:
        _LOGGER.warning(
            "No sensor entities were created! This might be normal if you have no sensor devices.",
        )
    else:
        for entity in entities[:10]:  # Log first 10 entities
            _LOGGER.debug("  Entity: %s", entity.name)

    async_add_entities(entities)
    _LOGGER.info("=" * 80)


class HeimanSensorEntity(CoordinatorEntity, SensorEntity):
    """Representation of a Heiman sensor."""

    def __init__(
        self,
        coordinator,
        device_info: dict,
        property_info: dict,
        cloud_client,
        i18n,
        devices_config: dict | None = None,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._device_info = device_info
        self._property_info = property_info
        self._cloud_client = cloud_client
        self._i18n = i18n
        self._devices_config = devices_config or {}

        property_id = property_info.get("id", "")
        property_name = property_info.get("name", "")

        # Get device ID from various possible fields (API uses 'id')
        device_id = device_info.get("id") or device_info.get("deviceId", "")
        device_name = (
            device_info.get("deviceName")
            or device_info.get("name")
            or device_info.get("productName", "Unknown")
        )
        device_model = (
            device_info.get("modelName")
            or device_info.get("model")
            or device_info.get("productName", "Unknown")
        )

        # Apply device config overrides if available
        device_config = self._devices_config.get(device_id, {})
        if device_config.get("name"):
            device_name = device_config["name"]

        # Use i18n to translate property name
        translated_property = i18n.translate_property(property_name)

        self._attr_unique_id = f"{device_id}_{property_id}"
        self._attr_name = (
            f"{device_name} {translated_property}"
            if translated_property
            else device_name
        )

        # Set icon from property info or use default icon based on property name
        self._attr_icon = property_info.get("icon") or _get_sensor_icon(property_info)
        if device_id == "1942869486798540800":
            _LOGGER.info("  Property %s has icon %s", property_name, self._attr_icon)
        # Build device info with area support and firmware version
        device_info_dict = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_name,
            "manufacturer": "Heiman",
            "model": device_model,
        }

        # Add firmware version if available
        sw_version = device_info.get("sw_version")
        if sw_version:
            device_info_dict["sw_version"] = sw_version
            _LOGGER.debug(
                "Added firmware version %s to device info for %s",
                sw_version,
                device_id,
            )

        # Add suggested_area from device config
        if device_config.get("area_id"):
            device_info_dict["suggested_area"] = device_config["area_id"]
        else:
            # Fallback to room name from device info
            room_name = device_info.get("room_name") or device_info.get("roomName", "")
            home_name = device_info.get("home_name") or device_info.get("homeName", "")
            if room_name and home_name:
                device_info_dict["suggested_area"] = f"{home_name} {room_name}"
            elif room_name:
                device_info_dict["suggested_area"] = room_name
            elif home_name:
                device_info_dict["suggested_area"] = home_name

        self._attr_device_info = device_info_dict
        self._attr_native_value = None

        # Set options for enum type sensors
        # Special handling for RSSI_Level - don't use predefined options since we translate values
        if "options" in property_info and property_name != "RSSI_Level":
            self._attr_options = property_info["options"]

        # Set device class for all sensors (including battery, signal_strength, etc.)
        if "device_class" in property_info:
            self._attr_device_class = property_info["device_class"]

        # Set unit of measurement if available
        # IMPORTANT: Don't set unit for non-numeric sensors to avoid HA numeric validation errors
        if "unit" in property_info and property_info.get("unit") is not None:
            # Only set unit if it's a valid unit (not a description text)
            unit_value = property_info["unit"]
            # Check if unit looks like a version string or description text
            if isinstance(unit_value, str):
                # Skip units that look like version numbers or descriptions
                # Extended keywords to filter out descriptive text used as unit
                skip_keywords = [
                    "版本",
                    "version",
                    "号",
                    "认证",
                    "firmware",
                    "列表",
                    "list",
                    "index",
                    "索引",
                    "名称",
                    "name",
                    "昵称",
                    "nickname",
                    "user",
                    "状态",
                    "status",
                    "type",
                    "类型",
                    "描述",
                    "description",
                    "info",
                    "信息",
                    "设备",
                    "device",
                    "host",
                    "主机",
                    "开关",
                    "switch",
                    "定时",
                    "timer",
                    "schedule",
                    "场景",
                    "scene",
                    "情景",
                    "mode",
                    "模式",
                    "配置",
                    "config",
                    "configuration",
                    "设置",
                    "setting",
                    "控制",
                    "control",
                    "管理",
                    "management",
                    "地址",
                    "address",
                    "mac",
                    "ip",  # Add address-related terms
                    "强度",
                    "strength",
                    "信号",
                    "signal",  # Add signal-related terms
                ]
                if any(skip_text in unit_value.lower() for skip_text in skip_keywords):
                    _LOGGER.debug(
                        "Skipping unit '%s' for sensor %s (appears to be descriptive text)",
                        unit_value,
                        self._attr_name,
                    )
                else:
                    self._attr_native_unit_of_measurement = unit_value
            else:
                self._attr_native_unit_of_measurement = unit_value
        else:
            # Try to translate unit from property name
            translated_unit = i18n.translate_unit(property_name)
            # Only use translated unit if it's not None and not descriptive text
            if translated_unit and isinstance(translated_unit, str):
                # Extended keywords to filter out descriptive text used as unit
                skip_keywords = [
                    "版本",
                    "version",
                    "号",
                    "认证",
                    "firmware",
                    "列表",
                    "list",
                    "index",
                    "索引",
                    "名称",
                    "name",
                    "昵称",
                    "nickname",
                    "user",
                    "状态",
                    "status",
                    "type",
                    "类型",
                    "描述",
                    "description",
                    "info",
                    "信息",
                    "设备",
                    "device",
                    "host",
                    "主机",
                    "开关",
                    "switch",
                    "定时",
                    "timer",
                    "schedule",
                    "场景",
                    "scene",
                    "情景",
                    "mode",
                    "模式",
                    "配置",
                    "config",
                    "configuration",
                    "设置",
                    "setting",
                    "控制",
                    "control",
                    "管理",
                    "management",
                    "地址",
                    "address",
                    "mac",
                    "ip",  # Add address-related terms
                    "强度",
                    "strength",
                    "信号",
                    "signal",  # Add signal-related terms
                ]
                if not any(
                    skip_text in translated_unit.lower() for skip_text in skip_keywords
                ):
                    self._attr_native_unit_of_measurement = translated_unit

        # Try to get initial value from coordinator cache
        if coordinator:
            self._update_from_cache()
            # If cache is empty, schedule a coordinator refresh to fetch initial data
            if not self._update_from_cache() and coordinator:
                _LOGGER.debug(
                    "Cache miss for %s during initialization, scheduling coordinator refresh",
                    self._attr_name,
                )
                # Schedule a refresh without awaiting (fire-and-forget)
                if hasattr(self, "hass") and self.hass:
                    self.hass.async_create_task(coordinator.async_refresh())

    # @property
    # def entity_picture(self) -> str | None:
    #     """Return the entity picture to use in the frontend.
    #
    #     Only returns device photo for main sensor entities.
    #     Returns None for diagnostic and functional sensors to use their custom icons instead.
    #     """
    #     # List of property IDs/names that should use custom icons instead of device photo
    #     # Include state and deviceType to avoid issues with enum type sensors
    #     icon_properties = {
    #         'time', 'zone', 'clock', 'temperature', 'temp', 'smoke',
    #         'device', 'info', 'version', 'master', 'gateway', 'battery',
    #         'rssi', 'signal', 'firmware', 'command', 'user', 'name',
    #         'rest', 'countdown', 'humidity', 'light', 'brightness',
    #         'illuminance', 'motion', 'door', 'window', 'contact',
    #         'water', 'leak', 'flood', 'gas', 'co', 'carbon',
    #         'state', 'online', 'devicetype', 'type'  # Add enum type properties
    #     }
    #
    #     property_id = self._property_info.get('id', '').lower()
    #     property_name = self._property_info.get('name', '').lower()
    #
    #     # Check if this property should use a custom icon
    #     check_text = f"{property_name} {property_id}".lower()
    #     if any(icon_prop in check_text for icon_prop in icon_properties):
    #         return None
    #
    #     # Get photoUrl from device info - check both direct field and nested fields
    #     photo_url = self._device_info.get('photoUrl')
    #     if photo_url:
    #         return photo_url
    #     # Also check in productInfo if available
    #     product_info = self._device_info.get('productInfo', {})
    #     if isinstance(product_info, dict):
    #         return product_info.get('photoUrl')
    #     return None

    def _normalize_sensor_value(self, value: Any) -> Any:
        """Normalize sensor value to a valid state type.

        Home Assistant sensor state must be a string or number.
        Lists and dicts are converted to JSON strings.
        Empty lists/dicts return None to avoid numeric conversion issues.
        """
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, dict)):
            # Empty collections should return None to avoid HA numeric conversion issues
            if len(value) == 0:
                return None
            # Convert non-empty complex types to JSON string
            try:
                return json.dumps(value, ensure_ascii=False)
            except TypeError, ValueError:
                return str(value)
        # Fallback for other types
        return str(value)

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Activity sensor is always available since it shows historical alarm data,
        not real-time device state.
        """
        return True

    @property
    def should_poll(self) -> bool:
        """Return if polling is needed."""
        # Disable polling - rely on MQTT push and coordinator refresh
        return False

    def _update_from_cache(self) -> bool:
        """Update entity state from coordinator cache (synchronous).

        Returns True if state was updated from cache, False if cache miss.
        This is used by both polling and MQTT push, but only reads from cache.
        For API fallback, use _fetch_from_api() in async contexts.
        Handles sub-properties with parent_property and json_field markers.
        """
        # Get device ID from various possible fields
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")
        property_name = self._property_info["id"]

        # Check if this is a sub-property (e.g., DeviceINFO_MAC)
        parent_property = self._property_info.get("parent_property")
        json_field = self._property_info.get("json_field")

        if parent_property and json_field:
            # This is a sub-property, need to extract from parent JSON
            _LOGGER.info(
                "Processing sub-property %s: parent=%s, field=%s",
                property_name,
                parent_property,
                json_field,
            )

            # Get parent property value from coordinator cache
            if self.coordinator and hasattr(self.coordinator, "get_device_property"):
                parent_value = self.coordinator.get_device_property(
                    device_id,
                    parent_property,
                )

                if parent_value is not None:
                    try:
                        # Parse parent JSON string
                        if isinstance(parent_value, str):
                            parent_data = json.loads(parent_value)
                        elif isinstance(parent_value, dict):
                            parent_data = parent_value
                        else:
                            _LOGGER.warning(
                                "Parent property %s has unexpected type %s: %s",
                                parent_property,
                                type(parent_value),
                                parent_value,
                            )
                            return False

                        # Extract the specific field
                        field_value = parent_data.get(json_field)

                        if field_value is not None:
                            # Special handling for DeviceINFO_DBM_Level - convert DBM to signal level
                            if property_name == "DeviceINFO_DBM_Level":
                                return self._update_dbm_level_from_device_info(
                                    field_value,
                                )

                            # Only update if value actually changed
                            normalized_value = self._normalize_sensor_value(field_value)
                            if self._attr_native_value != normalized_value:
                                self._attr_native_value = normalized_value
                                _LOGGER.debug(
                                    "Sub-property %s updated from parent %s: %s = %s",
                                    property_name,
                                    parent_property,
                                    json_field,
                                    field_value,
                                )
                            return True
                        _LOGGER.debug(
                            "Field %s not found in parent %s for device %s",
                            json_field,
                            parent_property,
                            device_id,
                        )
                    except json.JSONDecodeError as err:
                        _LOGGER.warning(
                            "Failed to parse parent JSON %s for sub-property %s: %s",
                            parent_property,
                            property_name,
                            err,
                        )
                    except Exception as err:  # noqa: BLE001
                        _LOGGER.warning(
                            "Error extracting field %s from parent %s for sub-property %s: %s",
                            json_field,
                            parent_property,
                            property_name,
                            err,
                        )
            return False

        # Check if this is a direct device info field (e.g., DeviceMac from macAddress field)
        # This is for properties that map directly to device info fields
        if json_field and not parent_property:
            _LOGGER.debug(
                "Processing direct device field %s: field=%s",
                property_name,
                json_field,
            )

            # Try common device info field names
            device_info_fields = [
                json_field,
                json_field.lower(),
                json_field.upper(),
                json_field.replace("_", ""),
                json_field.replace("_", " "),
            ]

            # Also add camelCase and PascalCase variations
            if "_" in json_field:
                parts = json_field.split("_")
                camel_case = parts[0].lower() + "".join(
                    word.capitalize() for word in parts[1:]
                )
                pascal_case = "".join(word.capitalize() for word in parts)
                device_info_fields.extend([camel_case, pascal_case])

            # Try to get value from device info
            for field in device_info_fields:
                field_value = self._device_info.get(field)
                if field_value is not None:
                    normalized_value = self._normalize_sensor_value(field_value)
                    if self._attr_native_value != normalized_value:
                        self._attr_native_value = normalized_value
                        _LOGGER.debug(
                            "Direct field %s updated from device info: %s = %s",
                            property_name,
                            field,
                            field_value,
                        )
                    return True

            _LOGGER.debug(
                "Field %s not found in device info for %s",
                json_field,
                property_name,
            )
            return False

        # Normal property (not a sub-property)
        # Get property value from coordinator cache
        if self.coordinator and hasattr(self.coordinator, "get_device_property"):
            cached_value = self.coordinator.get_device_property(
                device_id,
                property_name,
            )

            # Special handling for RSSI_Level - convert RSSI raw value to signal strength level
            if property_name == "RSSI_Level":
                return self._update_rssi_level_from_cache(device_id)

            if cached_value is not None:
                # Only update if value actually changed
                normalized_value = self._normalize_sensor_value(cached_value)
                if self._attr_native_value != normalized_value:
                    self._attr_native_value = normalized_value
                    _LOGGER.debug(
                        "Sensor %s updated from cache: %s = %s",
                        self._attr_name,
                        property_name,
                        cached_value,
                    )
                return True

        return False

    def _update_dbm_level_from_device_info(self, dbm_value) -> bool:
        """Update DeviceINFO_DBM signal strength level from device info.

        Converts DBM raw value (dBm) to signal strength level based on WiFi standards:
        - Strong (强): >= -76 dBm (excellent signal, close to AP)
        - Medium (中): -85 to -77 dBm (good signal for most uses)
        - Weak (弱): -95 to -86 dBm (poor signal, may have connectivity issues)
        - Very Weak (极弱): <= -96 dBm (very poor signal, near disconnection)

        Note: DBM values are negative dBm, so closer to 0 = stronger signal
        Example: -50 dBm is stronger than -80 dBm

        Returns True if state was updated, False otherwise.
        """
        try:
            # Convert DBM value to number if it's a string
            if isinstance(dbm_value, str):
                dbm_num = float(dbm_value)
            else:
                dbm_num = float(dbm_value)

            # Determine signal strength level and translate based on language
            # DBM is negative dBm, so closer to 0 = stronger signal
            if dbm_num >= -76:  # -76 to 0 dBm (Strong/Good signal)
                signal_level = "Excellent"
                if hasattr(self, "_i18n") and self._i18n:
                    translated = self._i18n.translate("status", "rssi_excellent")
                    if translated and translated != "rssi_excellent":
                        signal_level = translated
            elif (
                dbm_num >= -85 and dbm_num <= -77
            ):  # -85 to -77 dBm (Medium/Fair signal)
                signal_level = "Fair"
                if hasattr(self, "_i18n") and self._i18n:
                    translated = self._i18n.translate("status", "rssi_fair")
                    if translated and translated != "rssi_fair":
                        signal_level = translated
            elif dbm_num >= -95 and dbm_num <= -86:  # -95 to -86 dBm (Weak/Poor signal)
                signal_level = "Poor"
                if hasattr(self, "_i18n") and self._i18n:
                    translated = self._i18n.translate("status", "rssi_poor")
                    if translated and translated != "rssi_poor":
                        signal_level = translated
            else:  # <= -96 dBm (Very Weak/Very Poor signal)
                signal_level = "Very Poor"
                if hasattr(self, "_i18n") and self._i18n:
                    translated = self._i18n.translate("status", "rssi_very_poor")
                    if translated and translated != "rssi_very_poor":
                        signal_level = translated

            # Update sensor state if changed
            if self._attr_native_value != signal_level:
                self._attr_native_value = signal_level
                # Ensure options are cleared for DeviceINFO_DBM_Level to avoid validation errors
                if hasattr(self, "_attr_options") and self._attr_options:
                    self._attr_options = None
                _LOGGER.info(
                    "DBM signal level for device %s: %s dBm -> %s",
                    self._device_info.get("id", ""),
                    dbm_num,
                    signal_level,
                )
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Failed to convert DBM value %s to signal level: %s",
                dbm_value,
                err,
            )
            return False
        else:
            return True

    def _update_rssi_level_from_cache(self, device_id: str) -> bool:
        """Update RSSI signal strength level from cache.

        Converts RSSI raw value (dBm) to signal strength level based on WiFi standards:
        - Strong (强): >= -76 dBm (excellent signal, close to AP)
        - Medium (中): -85 to -77 dBm (good signal for most uses)
        - Weak (弱): -95 to -86 dBm (poor signal, may have connectivity issues)
        - Very Weak (极弱): <= -96 dBm (very poor signal, near disconnection)

        Note: RSSI values are negative dBm, so closer to 0 = stronger signal
        Example: -50 dBm is stronger than -80 dBm

        Returns True if state was updated, False otherwise.
        """
        if not self.coordinator or not hasattr(self.coordinator, "get_device_property"):
            return False

        # Get RSSI raw value from coordinator
        rssi_value = self.coordinator.get_device_property(device_id, "RSSI")
        _LOGGER.info("RSSI value for device %s: %s", device_id, rssi_value)
        if rssi_value is None:
            _LOGGER.debug("RSSI value not found in cache for device %s", device_id)
            return False

        try:
            # Convert RSSI value to number if it's a string
            if isinstance(rssi_value, str):
                rssi_num = float(rssi_value)
            else:
                rssi_num = float(rssi_value)

            # Determine signal strength level and translate based on language
            # RSSI is negative dBm, so closer to 0 = stronger signal
            if rssi_num >= 76:  # -76 to 0 dBm (Strong/Good signal)
                signal_level = "Excellent"
                if hasattr(self, "_i18n") and self._i18n:
                    translated = self._i18n.translate("status", "rssi_excellent")
                    if translated and translated != "rssi_excellent":
                        signal_level = translated
            elif (
                rssi_num >= 26 and rssi_num <= 75
            ):  # -85 to -77 dBm (Medium/Fair signal)
                signal_level = "Fair"
                if hasattr(self, "_i18n") and self._i18n:
                    translated = self._i18n.translate("status", "rssi_fair")
                    if translated and translated != "rssi_fair":
                        signal_level = translated
            elif rssi_num >= 26 and rssi_num <= 50:  # -95 to -86 dBm (Weak/Poor signal)
                signal_level = "Poor"
                if hasattr(self, "_i18n") and self._i18n:
                    translated = self._i18n.translate("status", "rssi_poor")
                    if translated and translated != "rssi_poor":
                        signal_level = translated
            else:  # <= -96 dBm (Very Weak/Very Poor signal)
                signal_level = "Very Poor"
                if hasattr(self, "_i18n") and self._i18n:
                    translated = self._i18n.translate("status", "rssi_very_poor")
                    if translated and translated != "rssi_very_poor":
                        signal_level = translated

            # Update sensor state if changed
            if self._attr_native_value != signal_level:
                self._attr_native_value = signal_level
                # Ensure options are cleared for RSSI_Level to avoid validation errors
                if hasattr(self, "_attr_options") and self._attr_options:
                    self._attr_options = None
                _LOGGER.info(
                    "RSSI signal level for device %s: %s dBm -> %s",
                    device_id,
                    rssi_num,
                    signal_level,
                )
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Failed to convert RSSI value %s to signal level for device %s: %s",
                rssi_value,
                device_id,
                err,
            )
            return False
        else:
            return True

    async def _fetch_from_api(self) -> bool:
        """Fetch property value from API (asynchronous fallback).

        Returns True if state was updated from API, False otherwise.
        """
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")
        property_name = self._property_info["id"]
        product_id = self._device_info.get("productId", "")

        _LOGGER.debug(
            "Sensor %s cache miss, falling back to individual API request",
            self._attr_name,
        )

        try:
            result = await self._cloud_client.async_read_device_property(
                product_id=product_id,
                device_id=device_id,
                property_name=property_name,
            )
            if result and "value" in result:
                self._attr_native_value = result["value"]
                _LOGGER.info(
                    "Sensor %s updated from API: %s = %s",
                    self._attr_name,
                    property_name,
                    result["value"],
                )
                return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Failed to fetch property %s for sensor %s: %s",
                property_name,
                self._attr_name,
                err,
            )

        return False

    async def async_update(self) -> None:
        """Update the entity state from coordinator cache (polling).

        This is called during polling by Home Assistant.
        Note: HA automatically calls async_write_ha_state() after async_update().
        """
        try:
            # Try cache first, then fallback to API
            if not self._update_from_cache():
                await self._fetch_from_api()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error updating sensor %s: %s", self._attr_name, err)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator (MQTT push).

        This is called when the coordinator has new data (e.g., from MQTT).
        Updates entity state immediately without waiting for next poll.
        Note: This is a sync callback, so we only read from cache.
        """
        try:
            # Only write state if cache update was successful (value changed)
            if self._update_from_cache():
                _LOGGER.debug(
                    "Sensor %s updated from coordinator (MQTT)",
                    self._attr_name,
                )
                # Write the new state to Home Assistant immediately
                self.async_write_ha_state()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error handling coordinator update for %s: %s",
                self._attr_name,
                err,
            )


class HeimanActivitySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Heiman device activity/alarm log sensor.

    This sensor displays recent alarm/activity logs for the device.
    """

    def __init__(
        self,
        coordinator,
        device_info: dict,
        cloud_client,
        i18n,
        devices_config: dict | None = None,
        max_alarms: int = 10,
    ) -> None:
        """Initialize activity sensor."""
        super().__init__(coordinator)
        self._device_info = device_info
        self._cloud_client = cloud_client
        self._i18n = i18n
        self._devices_config = devices_config or {}
        self._max_alarms = max_alarms

        # Get device ID from various possible fields (API uses 'id')
        device_id = device_info.get("id") or device_info.get("deviceId", "")
        device_name = (
            device_info.get("deviceName")
            or device_info.get("name")
            or device_info.get("productName", "Unknown")
        )
        device_model = (
            device_info.get("modelName")
            or device_info.get("model")
            or device_info.get("productName", "Unknown")
        )

        # Apply device config overrides if available
        device_config = self._devices_config.get(device_id, {})
        if device_config.get("name"):
            device_name = device_config["name"]

        # Use i18n to translate "Activity Log"
        activity_log_translated = (
            self._i18n.translate("entity", "sensor.activity.name")
            if hasattr(self, "_i18n") and self._i18n
            else "Activity Log"
        )
        if (
            not activity_log_translated
            or activity_log_translated == "sensor.activity.name"
        ):
            activity_log_translated = "Activity Log"

        self._attr_unique_id = f"{device_id}_activity"
        self._attr_name = f"{device_name} {activity_log_translated}"
        self._attr_icon = "mdi:bell-ring-outline"

        # Build device info with area support and firmware version
        device_info_dict = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_name,
            "manufacturer": "Heiman",
            "model": device_model,
        }

        # Add firmware version if available
        sw_version = device_info.get("sw_version")
        if sw_version:
            device_info_dict["sw_version"] = sw_version
            _LOGGER.debug(
                "Added firmware version %s to activity sensor device info for %s",
                sw_version,
                device_id,
            )

        # Add suggested_area from device config
        if device_config.get("area_id"):
            device_info_dict["suggested_area"] = device_config["area_id"]
        else:
            # Fallback to room name from device info
            room_name = device_info.get("room_name") or device_info.get("roomName", "")
            home_name = device_info.get("home_name") or device_info.get("homeName", "")
            if room_name and home_name:
                device_info_dict["suggested_area"] = f"{home_name} {room_name}"
            elif room_name:
                device_info_dict["suggested_area"] = room_name
            elif home_name:
                device_info_dict["suggested_area"] = home_name

        self._attr_device_info = device_info_dict
        self._attr_native_value = None
        self._alarms_cache: list[dict] = []

        # Store device_id for event callback filtering
        self._device_id = device_id

    async def async_update(self) -> None:
        """Fetch new alarm logs for the device (only called once during initialization)."""
        try:
            # Get device ID from various possible fields
            device_id = self._device_info.get("id") or self._device_info.get(
                "deviceId",
                "",
            )
            home_id = self._device_info.get("homeId") or self._cloud_client.home_id
            _LOGGER.info("Initial alarm fetch for device %s", device_id)
            result = await self._cloud_client.async_get_device_alarms(
                device_id=device_id,
                home_id=home_id,
                page_size=self._max_alarms,
                page_number=1,
            )
            if result and isinstance(result, dict):
                alarms = result.get("data", [])
                if isinstance(alarms, list):
                    self._alarms_cache = alarms
                    # Format the latest alarm as the state value
                    if alarms:
                        latest_alarm = alarms[0]
                        self._attr_native_value = self._format_alarm_summary(
                            latest_alarm,
                        )
                    else:
                        self._attr_native_value = self._i18n.translate_alarm(
                            "no_records",
                        )
                else:
                    self._attr_native_value = self._i18n.translate_alarm("no_records")
            else:
                self._attr_native_value = self._i18n.translate_alarm("no_records")
            _LOGGER.info(
                "Device %s initial alarm loaded: %s",
                device_id,
                self._attr_native_value,
            )

        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Failed to update activity sensor %s: %s", self._attr_name, err
            )
            self._attr_native_value = self._i18n.translate_alarm("fetch_failed")

    def _format_alarm_summary(self, alarm: dict) -> str:
        """Format an alarm record into a summary string."""
        title = alarm.get("title", self._i18n.translate_alarm("unknown_alarm"))
        alarm.get("contents", "")
        notify_time = alarm.get("createTime", 0)

        # Convert timestamp to readable format
        if notify_time:
            try:
                # notifyTime is in milliseconds
                dt = datetime.fromtimestamp(notify_time / 1000)
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError, OSError:
                time_str = self._i18n.translate_alarm("unknown_time")
        else:
            time_str = self._i18n.translate_alarm("unknown_time")

        return f"{time_str} - {title}"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes with alarm details."""
        attributes = {}

        if self._alarms_cache:
            # Add all alarms as JSON list
            alarms_list = []
            for alarm in self._alarms_cache:
                alarm_info = self._parse_alarm_info(alarm)
                alarms_list.append(alarm_info)

            attributes["alarms"] = alarms_list
            attributes["alarm_count"] = len(alarms_list)

            # Add formatted list for UI display
            attributes["alarms_formatted"] = self._format_alarms_for_display(
                alarms_list,
            )
        else:
            attributes["alarms"] = []
            attributes["alarm_count"] = 0
            attributes["alarms_formatted"] = self._i18n.translate_alarm(
                "no_records_yet",
            )

        return attributes

    def _parse_alarm_info(self, alarm: dict) -> dict:
        """Parse alarm record into structured info."""
        notify_time = alarm.get("createTime", 0)
        # Convert timestamp to readable format
        if notify_time:
            try:
                dt = datetime.fromtimestamp(notify_time / 1000)
                time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                date_str = dt.strftime("%Y-%m-%d")
            except ValueError, OSError:
                time_str = self._i18n.translate_alarm("unknown_time")
                date_str = self._i18n.translate_alarm("unknown_date")
        else:
            time_str = self._i18n.translate_alarm("unknown_time")
            date_str = self._i18n.translate_alarm("unknown_date")

        # Parse alarmInfo JSON if present
        alarm_details = {}
        alarm_info_str = alarm.get("alarmInfo", "")
        if alarm_info_str:
            with contextlib.suppress(json.JSONDecodeError):
                alarm_details = json.loads(alarm_info_str)

        return {
            "id": alarm.get("id", ""),
            "title": alarm.get("title", self._i18n.translate_alarm("unknown_alarm")),
            "contents": alarm.get("contents", ""),
            "level": alarm.get("level", 0),
            "time": time_str,
            "date": date_str,
            "timestamp": notify_time,
            "device_name": alarm.get("deviceName", ""),
            "source_type": alarm.get("sourceType", ""),
            "rule_name": alarm_details.get("ruleName", "")
            if isinstance(alarm_details, dict)
            else "",
        }

    def _format_alarms_for_display(self, alarms_list: list[dict]) -> str:
        """Format alarms list for display in UI."""
        if not alarms_list:
            return self._i18n.translate_alarm("no_records_yet")
        lines = []
        current_date = None

        for alarm in alarms_list:
            # Group by date
            if alarm["date"] != current_date:
                current_date = alarm["date"]
                lines.append(f"\n📅 {current_date}")

            # Format alarm entry
            level_icon = (
                "🔴" if alarm["level"] >= 4 else "🟡" if alarm["level"] >= 2 else "🟢"
            )
            lines.append(f"  {level_icon} {alarm['time']} - {alarm['title']}")
            if alarm["contents"]:
                # Extract useful info from contents (remove timestamp prefix)
                content = alarm["contents"]
                if "\n" in content:
                    content = content.split("\n")[-1]  # Get last line
                lines.append(f"     {content}")

        return "\n".join(lines)

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Activity sensor is always available since it shows historical alarm data,
        not real-time device state.
        """
        return True

    @property
    def should_poll(self) -> bool:
        """Return if polling is needed.

        Disable polling - alarms are updated via MQTT event messages only.
        Initial load happens once during entity setup.
        """
        return False

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to Home Assistant.

        Performs initial alarm fetch and registers for MQTT event callbacks.
        """
        await super().async_added_to_hass()

        _LOGGER.info(
            "Activity sensor %s added to HA, starting initialization",
            self._device_id,
        )

        # Fetch alarms once during initialization
        _LOGGER.info("Fetching initial alarms for device %s", self._device_id)
        await self.async_update()

        # Register event callback with coordinator
        if hasattr(self.coordinator, "mqtt_client") and self.coordinator.mqtt_client:
            _LOGGER.info(
                "Registering global event callback for activity sensor %s",
                self._device_id,
            )
            self.coordinator.mqtt_client.register_event_callback(
                event_type=None,  # Listen to all events
                callback=self._on_event_received,
            )
            _LOGGER.info(
                "Event callback registered successfully for device %s",
                self._device_id,
            )
        else:
            _LOGGER.warning(
                "MQTT client not available, cannot register event callback for device %s",
                self._device_id,
            )

    def _on_event_received(self, device_id: str, payload: dict) -> None:
        """Handle MQTT event message.

        Only refreshes alarms if the event is for this specific device.
        Adds a delay to allow backend to process the event first.

        Args:
            device_id: The device ID that triggered the event
            payload: Event payload data
        """
        _LOGGER.info(
            "_on_event_received called: event_device_id=%s, my_device_id=%s",
            device_id,
            self._device_id,
        )

        # Only process events for this device
        if device_id != self._device_id:
            _LOGGER.debug(
                "Device ID mismatch, ignoring event for activity sensor %s",
                self._device_id,
            )
            return

        _LOGGER.info(
            "Event received for device %s, scheduling alarm refresh with 400ms delay",
            device_id,
        )

        # Schedule alarm refresh with delay to allow backend to process event first
        # Use asyncio.run_coroutine_threadsafe for thread-safe execution from MQTT callback
        if self.hass and hasattr(self.hass, "loop"):

            async def delayed_refresh():
                await asyncio.sleep(0.4)  # 400ms delay
                await self._async_refresh_alarms()

            _LOGGER.info(
                "Scheduling delayed alarm refresh task for device %s (thread-safe, 400ms delay)",
                device_id,
            )
            asyncio.run_coroutine_threadsafe(delayed_refresh(), self.hass.loop)
        else:
            _LOGGER.error(
                "HASS or event loop not available, cannot schedule alarm refresh",
            )

    async def _async_refresh_alarms(self) -> None:
        """Refresh alarms from API."""
        _LOGGER.info("_async_refresh_alarms started for device %s", self._device_id)
        try:
            home_id = self._device_info.get("homeId") or self._cloud_client.home_id
            _LOGGER.info(
                "Fetching alarms for device %s, home_id=%s",
                self._device_id,
                home_id,
            )
            result = await self._cloud_client.async_get_device_alarms(
                device_id=self._device_id,
                home_id=home_id,
                page_size=self._max_alarms,
                page_number=1,
            )
            _LOGGER.info(
                "Alarms fetch completed for device %s, result type: %s",
                self._device_id,
                type(result),
            )
            if result and isinstance(result, dict):
                alarms = result.get("data", [])
                _LOGGER.info(
                    "Got %d alarms for device %s",
                    len(alarms),
                    self._device_id,
                )
                if isinstance(alarms, list) and alarms:
                    self._alarms_cache = alarms
                    latest_alarm = alarms[0]
                    self._attr_native_value = self._format_alarm_summary(latest_alarm)
                    _LOGGER.info(
                        "Device %s alarms refreshed: %s",
                        self._device_id,
                        self._attr_native_value,
                    )
                    self.async_write_ha_state()
                    _LOGGER.info("HA state updated for device %s", self._device_id)
                else:
                    _LOGGER.info("No alarms found for device %s", self._device_id)
            else:
                _LOGGER.warning(
                    "Invalid result format for device %s: %s",
                    self._device_id,
                    result,
                )
        except Exception:
            _LOGGER.exception(
                "Failed to refresh alarms for device %s",
                self._device_id,
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator (MQTT push).

        For activity sensor, coordinator updates trigger a fresh alarm fetch
        via the event callback mechanism.
        """
        # Activity sensor doesn't use coordinator cache for its main value
        # It relies on event-driven updates via _on_event_received
        # This method is kept for compatibility but doesn't do anything
        _LOGGER.debug(
            "Activity sensor %s received coordinator update (ignored, using event-driven updates)",
            self._device_id,
        )


def _get_sensor_icon(property_info: dict) -> str | None:
    """Get icon for sensor entity based on property name.

    Args:
        property_info: Property information dictionary containing 'name' or 'id'

    Returns:
        MDI icon string or None to use default icon
    """
    property_name = property_info.get("name", "").lower()
    property_id = property_info.get("id", "").lower()

    # Check both name and id fields
    check_text = f"{property_name} {property_id}".lower()

    # Time-related sensors (Set Time, Time Zone)
    if "time" in check_text or "zone" in check_text or "clock" in check_text:
        return "mdi:clock"

    # Temperature sensors
    if "temperature" in check_text or "temp" in check_text:
        return "mdi:thermometer"

    # Smoke detector
    if "smoke" in check_text:
        return "mdi:smoke-detector"

    # Device info sensors
    if "device" in check_text and ("info" in check_text or "version" in check_text):
        return "mdi:information-outline"

    # Master device
    if "master" in check_text:
        return "mdi:router-wireless"

    # Gateway sensors
    if "gateway" in check_text:
        return "mdi:gateway"

    # Battery sensors
    if "battery" in check_text:
        return "mdi:battery"

    # Signal strength (RSSI)
    if "rssi" in check_text or "signal" in check_text:
        return "mdi:signal"

    # Firmware version
    if "firmware" in check_text or "version" in check_text:
        return "mdi:chip"

    # Command sensors
    if "command" in check_text:
        return "mdi:remote"

    # User-related sensors
    if "user" in check_text or "name" in check_text:
        return "mdi:account"

    # Rest times/countdown
    if "rest" in check_text or "countdown" in check_text:
        return "mdi:timer-sand"

    # Humidity sensors
    if "humidity" in check_text:
        return "mdi:water-percent"

    # Light/brightness sensors
    if (
        "light" in check_text
        or "brightness" in check_text
        or "illuminance" in check_text
    ):
        return "mdi:brightness-6"

    # Motion sensors
    if "motion" in check_text:
        return "mdi:motion-sensor"

    # Door/window contact sensors
    if "door" in check_text or "window" in check_text or "contact" in check_text:
        return "mdi:door"

    # Water leak sensors
    if "water" in check_text or "leak" in check_text or "flood" in check_text:
        return "mdi:water-alert"

    # Gas/CO/CO2 sensors
    if "gas" in check_text or "co" in check_text or "carbon" in check_text:
        return "mdi:gas-cylinder"
    # Fault sensors
    if "fault" in check_text:
        return "mdi:alert"
    # Index sensors
    if "index" in check_text:
        return "mdi:numeric"
    # Default: use generic sensor icon
    return "mdi:gauge"
