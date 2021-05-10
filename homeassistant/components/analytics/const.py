"""Constants for the analytics integration."""
from datetime import timedelta
import logging

import voluptuous as vol

ANALYTICS_ENDPOINT_URL = "https://analytics-api.home-assistant.io/v1"
ANALYTICS_ENDPOINT_URL_DEV = "https://analytics-api-dev.home-assistant.io/v1"
DOMAIN = "analytics"
INTERVAL = timedelta(days=1)
STORAGE_KEY = "core.analytics"
STORAGE_VERSION = 1


LOGGER: logging.Logger = logging.getLogger(__package__)

ATTR_ADDON_COUNT = "addon_count"
ATTR_ADDONS = "addons"
ATTR_AUTO_UPDATE = "auto_update"
ATTR_AUTOMATION_COUNT = "automation_count"
ATTR_BASE = "base"
ATTR_BOARD = "board"
ATTR_CUSTOM_INTEGRATIONS = "custom_integrations"
ATTR_DIAGNOSTICS = "diagnostics"
ATTR_HEALTHY = "healthy"
ATTR_INSTALLATION_TYPE = "installation_type"
ATTR_INTEGRATION_COUNT = "integration_count"
ATTR_INTEGRATIONS = "integrations"
ATTR_ONBOARDED = "onboarded"
ATTR_OPERATING_SYSTEM = "operating_system"
ATTR_PREFERENCES = "preferences"
ATTR_PROTECTED = "protected"
ATTR_SLUG = "slug"
ATTR_STATE_COUNT = "state_count"
ATTR_STATISTICS = "statistics"
ATTR_SUPERVISOR = "supervisor"
ATTR_SUPPORTED = "supported"
ATTR_USAGE = "usage"
ATTR_USER_COUNT = "user_count"
ATTR_UUID = "uuid"
ATTR_VERSION = "version"


PREFERENCE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_BASE): bool,
        vol.Optional(ATTR_DIAGNOSTICS): bool,
        vol.Optional(ATTR_STATISTICS): bool,
        vol.Optional(ATTR_USAGE): bool,
    }
)
