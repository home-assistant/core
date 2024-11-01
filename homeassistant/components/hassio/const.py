"""Hass.io const variables."""

from datetime import timedelta
from enum import StrEnum

DOMAIN = "hassio"

ATTR_ADDON = "addon"
ATTR_ADDONS = "addons"
ATTR_ADMIN = "admin"
ATTR_COMPRESSED = "compressed"
ATTR_CONFIG = "config"
ATTR_DATA = "data"
ATTR_SESSION_DATA_USER_ID = "user_id"
ATTR_DISCOVERY = "discovery"
ATTR_ENABLE = "enable"
ATTR_ENDPOINT = "endpoint"
ATTR_FOLDERS = "folders"
ATTR_HEALTHY = "healthy"
ATTR_HOMEASSISTANT = "homeassistant"
ATTR_HOMEASSISTANT_EXCLUDE_DATABASE = "homeassistant_exclude_database"
ATTR_INPUT = "input"
ATTR_ISSUES = "issues"
ATTR_MESSAGE = "message"
ATTR_METHOD = "method"
ATTR_PANELS = "panels"
ATTR_PASSWORD = "password"
ATTR_RESULT = "result"
ATTR_SUGGESTIONS = "suggestions"
ATTR_SUPPORTED = "supported"
ATTR_TIMEOUT = "timeout"
ATTR_TITLE = "title"
ATTR_UNHEALTHY = "unhealthy"
ATTR_UNHEALTHY_REASONS = "unhealthy_reasons"
ATTR_UNSUPPORTED = "unsupported"
ATTR_UNSUPPORTED_REASONS = "unsupported_reasons"
ATTR_UPDATE_KEY = "update_key"
ATTR_USERNAME = "username"
ATTR_UUID = "uuid"
ATTR_WS_EVENT = "event"

X_AUTH_TOKEN = "X-Supervisor-Token"
X_INGRESS_PATH = "X-Ingress-Path"
X_HASS_USER_ID = "X-Hass-User-ID"
X_HASS_IS_ADMIN = "X-Hass-Is-Admin"
X_HASS_SOURCE = "X-Hass-Source"

WS_TYPE = "type"
WS_ID = "id"

WS_TYPE_API = "supervisor/api"
WS_TYPE_EVENT = "supervisor/event"
WS_TYPE_SUBSCRIBE = "supervisor/subscribe"

EVENT_SUPERVISOR_EVENT = "supervisor_event"
EVENT_SUPERVISOR_UPDATE = "supervisor_update"
EVENT_HEALTH_CHANGED = "health_changed"
EVENT_SUPPORTED_CHANGED = "supported_changed"
EVENT_ISSUE_CHANGED = "issue_changed"
EVENT_ISSUE_REMOVED = "issue_removed"

UPDATE_KEY_SUPERVISOR = "supervisor"

ADDONS_COORDINATOR = "hassio_addons_coordinator"


DATA_CORE_INFO = "hassio_core_info"
DATA_CORE_STATS = "hassio_core_stats"
DATA_HOST_INFO = "hassio_host_info"
DATA_STORE = "hassio_store"
DATA_INFO = "hassio_info"
DATA_OS_INFO = "hassio_os_info"
DATA_NETWORK_INFO = "hassio_network_info"
DATA_SUPERVISOR_INFO = "hassio_supervisor_info"
DATA_SUPERVISOR_STATS = "hassio_supervisor_stats"
DATA_ADDONS_CHANGELOGS = "hassio_addons_changelogs"
DATA_ADDONS_INFO = "hassio_addons_info"
DATA_ADDONS_STATS = "hassio_addons_stats"
HASSIO_UPDATE_INTERVAL = timedelta(minutes=5)

ATTR_AUTO_UPDATE = "auto_update"
ATTR_VERSION = "version"
ATTR_VERSION_LATEST = "version_latest"
ATTR_CPU_PERCENT = "cpu_percent"
ATTR_CHANGELOG = "changelog"
ATTR_LOCATION = "location"
ATTR_MEMORY_PERCENT = "memory_percent"
ATTR_SLUG = "slug"
ATTR_STATE = "state"
ATTR_STARTED = "started"
ATTR_URL = "url"
ATTR_REPOSITORY = "repository"

DATA_KEY_ADDONS = "addons"
DATA_KEY_OS = "os"
DATA_KEY_SUPERVISOR = "supervisor"
DATA_KEY_CORE = "core"
DATA_KEY_HOST = "host"
DATA_KEY_SUPERVISOR_ISSUES = "supervisor_issues"

PLACEHOLDER_KEY_ADDON = "addon"
PLACEHOLDER_KEY_ADDON_URL = "addon_url"
PLACEHOLDER_KEY_REFERENCE = "reference"
PLACEHOLDER_KEY_COMPONENTS = "components"

ISSUE_KEY_SYSTEM_DOCKER_CONFIG = "issue_system_docker_config"
ISSUE_KEY_ADDON_DETACHED_ADDON_MISSING = "issue_addon_detached_addon_missing"
ISSUE_KEY_ADDON_DETACHED_ADDON_REMOVED = "issue_addon_detached_addon_removed"

CORE_CONTAINER = "homeassistant"
SUPERVISOR_CONTAINER = "hassio_supervisor"

CONTAINER_STATS = "stats"
CONTAINER_CHANGELOG = "changelog"
CONTAINER_INFO = "info"

# This is a mapping of which endpoint the key in the addon data
# is obtained from so we know which endpoint to update when the
# coordinator polls for updates.
KEY_TO_UPDATE_TYPES: dict[str, set[str]] = {
    ATTR_VERSION_LATEST: {CONTAINER_INFO, CONTAINER_CHANGELOG},
    ATTR_MEMORY_PERCENT: {CONTAINER_STATS},
    ATTR_CPU_PERCENT: {CONTAINER_STATS},
    ATTR_VERSION: {CONTAINER_INFO},
    ATTR_STATE: {CONTAINER_INFO},
}

REQUEST_REFRESH_DELAY = 10


class SupervisorEntityModel(StrEnum):
    """Supervisor entity model."""

    ADDON = "Home Assistant Add-on"
    OS = "Home Assistant Operating System"
    CORE = "Home Assistant Core"
    SUPERVIOSR = "Home Assistant Supervisor"
    HOST = "Home Assistant Host"


class SupervisorIssueContext(StrEnum):
    """Context for supervisor issues."""

    ADDON = "addon"
    CORE = "core"
    DNS_SERVER = "dns_server"
    MOUNT = "mount"
    OS = "os"
    PLUGIN = "plugin"
    SUPERVISOR = "supervisor"
    STORE = "store"
    SYSTEM = "system"
