"""Constants for the analytics integration."""

from datetime import timedelta
import logging

import voluptuous as vol

DOMAIN = "analytics"
INTERVAL = timedelta(days=1)
STORAGE_KEY = "core.analytics"
STORAGE_VERSION = 1

BASIC_ENDPOINT_URL = "https://analytics-api.home-assistant.io/v1"
BASIC_ENDPOINT_URL_DEV = "https://analytics-api-dev.home-assistant.io/v1"

SNAPSHOT_VERSION = 1
SNAPSHOT_DEFAULT_URL = "https://device-database.eco-dev-aws.openhomefoundation.com"
SNAPSHOT_URL_PATH = f"/api/v1/snapshot/{SNAPSHOT_VERSION}"

LOGGER: logging.Logger = logging.getLogger(__package__)

ATTR_ADDON_COUNT = "addon_count"
ATTR_ADDONS = "addons"
ATTR_ARCH = "arch"
ATTR_AUTO_UPDATE = "auto_update"
ATTR_AUTOMATION_COUNT = "automation_count"
ATTR_BASE = "base"
ATTR_BOARD = "board"
ATTR_CERTIFICATE = "certificate"
ATTR_CONFIGURED = "configured"
ATTR_CUSTOM_INTEGRATIONS = "custom_integrations"
ATTR_DIAGNOSTICS = "diagnostics"
ATTR_ENERGY = "energy"
ATTR_ENGINE = "engine"
ATTR_HEALTHY = "healthy"
ATTR_INSTALLATION_TYPE = "installation_type"
ATTR_INTEGRATION_COUNT = "integration_count"
ATTR_INTEGRATIONS = "integrations"
ATTR_ONBOARDED = "onboarded"
ATTR_OPERATING_SYSTEM = "operating_system"
ATTR_PREFERENCES = "preferences"
ATTR_PROTECTED = "protected"
ATTR_RECORDER = "recorder"
ATTR_SLUG = "slug"
ATTR_SNAPSHOTS = "snapshots"
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
        vol.Optional(ATTR_SNAPSHOTS): bool,
        vol.Optional(ATTR_DIAGNOSTICS): bool,
        vol.Optional(ATTR_STATISTICS): bool,
        vol.Optional(ATTR_USAGE): bool,
    }
)
