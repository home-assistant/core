"""Constants for the analytics integration."""
from datetime import timedelta
from enum import Enum
import logging

ANALYTICS_ENPOINT_URL = "https://floral-resonance-f63b.ludeeus.workers.dev"
DOMAIN = "analytics"
INTERVAL = timedelta(days=1)
STORAGE_KEY = "core.analytics"
STORAGE_VERSION = 1


LOGGER: logging.Logger = logging.getLogger(__package__)

ATTR_ADDON_COUNT = "addon_count"
ATTR_ADDONS = "addons"
ATTR_AUTOMATION_COUNT = "automation_count"
ATTR_AUTO_UPDATE = "auto_update"
ATTR_DIAGNOSTICS = "diagnostics"
ATTR_HEALTHY = "healthy"
ATTR_HUUID = "huuid"
ATTR_INSTALLATION_TYPE = "installation_type"
ATTR_INTEGRATION_COUNT = "integration_count"
ATTR_INTEGRATIONS = "integrations"
ATTR_ONBOARDED = "onboarded"
ATTR_PREFERENCES = "preferences"
ATTR_PROTECTED = "protected"
ATTR_SLUG = "slug"
ATTR_STATE_COUNT = "state_count"
ATTR_SUPERVISOR = "supervisor"
ATTR_SUPPORTED = "supported"
ATTR_USER_COUNT = "user_count"
ATTR_VERSION = "version"


class AnalyticsPreference(str, Enum):
    """Analytics prefrences."""

    BASE = "base"
    DIAGNOSTICS = "diagnostics"
    STATISTICS = "statistics"
    USAGE = "usage"


INGORED_DOMAINS = [
    "air_quality",
    "alarm_control_panel",
    "analytics",
    "api",
    "auth",
    "binary_sensor",
    "calendar",
    "camera",
    "climate",
    "config",
    "cover",
    "demo",
    "device_automation",
    "device_tracker",
    "fan",
    "hassio",
    "homeassistant",
    "http",
    "humidifier",
    "image_processing",
    "image",
    "light",
    "lock",
    "logger",
    "lovelace",
    "media_player",
    "notify",
    "number",
    "onboarding",
    "persistent_notification",
    "recorder",
    "search",
    "sensor",
    "switch",
    "system_log",
    "tts",
    "vacuum",
    "water_heater",
    "weather",
    "websocket_api",
]
