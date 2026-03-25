"""Internationalization utilities for Heiman Home integration."""

import logging
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Translation dictionaries
TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = {
    "zh-Hans": {
        "oauth2": {
            "success": {
                "title": "认证成功",
                "content": "认证成功。请关闭此页面并返回 Home Assistant 继续。",
                "button": "关闭页面",
            },
            "fail": {
                "title": "认证失败",
                "content": "认证失败: {error_msg}。请关闭此页面并重试。",
                "button": "关闭页面",
            },
            "error_msg": {
                "100": "输入参数无效",
                "101": "状态参数无效",
                "102": "配置流程错误",
                "200": "认证失败",
                "201": "OAuth2 响应无效",
                "202": "授权码无效",
                "203": "刷新令牌无效",
                "300": "HTTP 请求错误",
                "301": "未授权访问",
                "302": "访问令牌无效",
                "500": "JSON 解码错误",
            },
        },
        "device_type": {
            "sensor": "传感器",
            "binary_sensor": "二进制传感器",
            "switch": "开关",
            "climate": "空调",
            "light": "灯光",
            "fan": "风扇",
            "cover": "窗帘",
            "lock": "门锁",
            "camera": "摄像头",
        },
        "property": {
            "temperature": "温度",
            "humidity": "湿度",
            "battery": "电池",
            "signal_strength": "信号强度",
            "power_state": "电源状态",
            "smoke": "烟雾",
            "motion": "移动",
            "door": "门窗",
            "water_leak": "水浸",
            "co": "一氧化碳",
            "switch_state": "开关状态",
        },
        "status": {
            "on": "开启",
            "off": "关闭",
            "online": "在线",
            "offline": "离线",
            "detected": "检测到",
            "normal": "正常",
            "alarm": "报警",
            "rssi_excellent": "强",
            "rssi_good": "强",
            "rssi_fair": "中",
            "rssi_poor": "弱",
            "rssi_very_poor": "极弱",
        },
        "unit": {
            "temperature": "°C",
            "humidity": "%",
            "battery": "%",
            "signal_strength": "dBm",
        },
        "alarm": {
            "no_records": "无告警记录",
            "fetch_failed": "获取失败",
            "unknown_alarm": "未知告警",
            "unknown_time": "未知时间",
            "unknown_date": "未知日期",
            "no_records_yet": "暂无告警记录",
        },
    },
    "en": {
        "oauth2": {
            "success": {
                "title": "Authentication Successful",
                "content": "Authentication was successful. Please close this page and return to Home Assistant to continue.",
                "button": "Close Page",
            },
            "fail": {
                "title": "Authentication Failed",
                "content": "Authentication failed: {error_msg}. Please close this page and try again.",
                "button": "Close Page",
            },
            "error_msg": {
                "100": "Invalid input parameter",
                "101": "Invalid state parameter",
                "102": "Configuration flow error",
                "200": "Authentication failed",
                "201": "Invalid OAuth2 response",
                "202": "Invalid authorization code",
                "203": "Invalid refresh token",
                "300": "HTTP request error",
                "301": "Unauthorized access",
                "302": "Invalid access token",
                "500": "JSON decode error",
            },
        },
        "device_type": {
            "sensor": "Sensor",
            "binary_sensor": "Binary Sensor",
            "switch": "Switch",
            "climate": "Climate",
            "light": "Light",
            "fan": "Fan",
            "cover": "Cover",
            "lock": "Lock",
            "camera": "Camera",
        },
        "property": {
            "temperature": "Temperature",
            "humidity": "Humidity",
            "battery": "Battery",
            "signal_strength": "Signal Strength",
            "power_state": "Power State",
            "smoke": "Smoke",
            "motion": "Motion",
            "door": "Door",
            "water_leak": "Water Leak",
            "co": "CO",
            "switch_state": "Switch State",
        },
        "status": {
            "on": "On",
            "off": "Off",
            "online": "Online",
            "offline": "Offline",
            "detected": "Detected",
            "normal": "Normal",
            "alarm": "Alarm",
            "rssi_excellent": "Excellent",
            "rssi_good": "Good",
            "rssi_fair": "Fair",
            "rssi_poor": "Poor",
            "rssi_very_poor": "Very Poor",
        },
        "unit": {
            "temperature": "°C",
            "humidity": "%",
            "battery": "%",
            "signal_strength": "dBm",
        },
        "alarm": {
            "no_records": "No Alarm Records",
            "fetch_failed": "Fetch Failed",
            "unknown_alarm": "Unknown Alarm",
            "unknown_time": "Unknown Time",
            "unknown_date": "Unknown Date",
            "no_records_yet": "No Alarm Records Yet",
        },
    },
}


class HeimanI18n:
    """Internationalization manager for Heiman Home."""

    def __init__(self, language: str = "en", loop=None):
        """Initialize i18n manager."""
        self._language = language
        self._loop = loop
        self._translations = TRANSLATIONS.get(language, TRANSLATIONS.get("en", {}))

    async def init_async(self) -> None:
        """Async initialization method (compatibility)."""
        # This method exists for compatibility with config_flow
        # No actual async initialization needed

    async def deinit_async(self) -> None:
        """Async cleanup method (compatibility)."""
        # This method exists for compatibility with config_flow
        # No actual async cleanup needed

    def translate(
        self,
        category: str = "",
        key: str = "",
        default: str | None = None,
    ) -> dict | None | str:
        """Translate a key or get a nested translation dictionary.

        Args:
            category: Top-level category (e.g., 'oauth2', 'config')
            key: Nested key path (e.g., 'success.title') or empty to return whole category
            default: Default value if translation not found

        Returns:
            Translated string or dict if no specific key provided
        """
        # Handle chain-style calls: translate('oauth2.success')
        if not key and "." in category:
            parts = category.split(".", 2)
            category = parts[0]
            key = parts[1] if len(parts) > 1 else ""

        if not category:
            return default or {}

        category_data = self._translations.get(category)
        if not category_data:
            # Fall back to English translations
            category_data = TRANSLATIONS.get("en", {}).get(category)

        if not category_data:
            return default or (key or {})

        # If no key specified, return the whole category as dict
        if not key:
            return category_data

        # Handle nested keys like 'success.title'
        if "." in key:
            parts = key.split(".")
            value = category_data
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default or key
            return value

        # Simple key lookup
        value = category_data.get(key)
        return value if value is not None else (default or key)

    def translate_device_type(self, device_type: str) -> str:
        """Translate device type."""
        return self.translate("device_type", device_type, device_type)

    def translate_property(self, property_name: str) -> str:
        """Translate property name."""
        return self.translate("property", property_name, property_name)

    def translate_status(self, status: str) -> str:
        """Translate status."""
        return self.translate("status", status, status)

    def translate_unit(self, unit: str) -> str:
        """Translate unit."""
        return self.translate("unit", unit, unit)

    def translate_alarm(self, key: str) -> str:
        """Translate alarm-related text."""
        return self.translate("alarm", key, key)

    def translate_rssi_level(self, rssi_value: float) -> str:
        """Translate RSSI signal strength level.

        Args:
            rssi_value: RSSI value in dBm (negative number)

        Returns:
            Translated signal strength level
        """
        if rssi_value >= -76:  # -76 to 0 dBm (Strong/Good signal)
            return self.translate_status("rssi_excellent") or "Excellent"
        if (
            rssi_value >= -85 and rssi_value <= -77
        ):  # -85 to -77 dBm (Medium/Fair signal)
            return self.translate_status("rssi_fair") or "Fair"
        if rssi_value >= -95 and rssi_value <= -86:  # -95 to -86 dBm (Weak/Poor signal)
            return self.translate_status("rssi_poor") or "Poor"
        # <= -96 dBm (Very Weak/Very Poor signal)
        return self.translate_status("rssi_very_poor") or "Very Poor"

    def format_property_name(
        self,
        property_name: str,
        device_name: str | None = None,
    ) -> str:
        """Format a property name for display."""
        translated = self.translate_property(property_name)
        if device_name:
            return f"{device_name} {translated}"
        return translated

    def format_device_name(
        self,
        device_name: str,
        device_type: str | None = None,
    ) -> str:
        """Format a device name for display."""
        if device_type:
            translated_type = self.translate_device_type(device_type)
            return f"{device_name} ({translated_type})"
        return device_name

    def get_available_languages(self) -> list[str]:
        """Get list of available languages."""
        return list(TRANSLATIONS.keys())

    def set_language(self, language: str) -> None:
        """Change current language."""
        if language in TRANSLATIONS:
            self._language = language
            self._translations = TRANSLATIONS[language]
        else:
            _LOGGER.warning("Language '%s' not available, using 'en'", language)
            self._language = "en"
            self._translations = TRANSLATIONS["en"]


def get_i18n(language: str = "en") -> HeimanI18n:
    """Get i18n manager for specified language."""
    return HeimanI18n(language)


def translate_status_value(value: Any, language: str = "en") -> str:
    """Translate a boolean status value."""
    i18n = get_i18n(language)
    if value is True or value in {1, "on", "1"}:
        return i18n.translate_status("on")
    if value is False or value in {0, "off", "0"}:
        return i18n.translate_status("off")
    return str(value)


def get_ha_language(hass: HomeAssistant) -> str:
    """Get Home Assistant language preference."""
    # Get the language from HA config, default to en
    language = hass.config.language
    if language and language in TRANSLATIONS:
        return language
    return "en"
