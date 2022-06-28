"""Hass.io const variables."""
from enum import Enum

DOMAIN = "hassio"

ATTR_ADDON = "addon"
ATTR_ADDONS = "addons"
ATTR_ADMIN = "admin"
ATTR_COMPRESSED = "compressed"
ATTR_CONFIG = "config"
ATTR_DATA = "data"
ATTR_DISCOVERY = "discovery"
ATTR_ENABLE = "enable"
ATTR_FOLDERS = "folders"
ATTR_HOMEASSISTANT = "homeassistant"
ATTR_INPUT = "input"
ATTR_PANELS = "panels"
ATTR_PASSWORD = "password"
ATTR_TITLE = "title"
ATTR_USERNAME = "username"
ATTR_UUID = "uuid"
ATTR_WS_EVENT = "event"
ATTR_ENDPOINT = "endpoint"
ATTR_METHOD = "method"
ATTR_RESULT = "result"
ATTR_TIMEOUT = "timeout"

X_AUTH_TOKEN = "X-Supervisor-Token"
X_INGRESS_PATH = "X-Ingress-Path"
X_HASS_USER_ID = "X-Hass-User-ID"
X_HASS_IS_ADMIN = "X-Hass-Is-Admin"

WS_TYPE = "type"
WS_ID = "id"

WS_TYPE_API = "supervisor/api"
WS_TYPE_EVENT = "supervisor/event"
WS_TYPE_SUBSCRIBE = "supervisor/subscribe"

EVENT_SUPERVISOR_EVENT = "supervisor_event"

ATTR_AUTO_UPDATE = "auto_update"
ATTR_VERSION = "version"
ATTR_VERSION_LATEST = "version_latest"
ATTR_UPDATE_AVAILABLE = "update_available"
ATTR_CPU_PERCENT = "cpu_percent"
ATTR_CHANGELOG = "changelog"
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


class SupervisorEntityModel(str, Enum):
    """Supervisor entity model."""

    ADDON = "Home Assistant Add-on"
    OS = "Home Assistant Operating System"
    CORE = "Home Assistant Core"
    SUPERVIOSR = "Home Assistant Supervisor"
