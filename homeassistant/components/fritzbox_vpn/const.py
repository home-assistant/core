"""Constants for FritzBox VPN integration."""

from collections.abc import Mapping
from typing import Any

from fritzboxvpn import const as fritzboxvpn_const
from homeassistant.const import CONF_HOST, CONF_PASSWORD

DEFAULT_NAME_UNKNOWN = fritzboxvpn_const.DEFAULT_NAME_UNKNOWN
NAME_FRITZBOX = fritzboxvpn_const.NAME_FRITZBOX

DOMAIN = "fritzbox_vpn"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_HOST = "192.168.178.1"
HOST_FALLBACK_UNKNOWN = "unknown"
DEFAULT_UPDATE_INTERVAL = 30
UPDATE_INTERVAL_MIN = 5
UPDATE_INTERVAL_MAX = 3600
RETRY_AFTER_SECONDS = 300

ATTR_UID = "uid"
ATTR_VPN_UID = "vpn_uid"
ATTR_STATUS = "status"
UNIQUE_ID_PREFIX = f"{DOMAIN}_"
UNIQUE_ID_SUFFIX_SWITCH = "switch"
UNIQUE_ID_SUFFIX_STATUS = "status"
UNIQUE_ID_SUFFIX_UID = "uid"
UNIQUE_ID_SUFFIX_VPN_UID = "vpn_uid"
UNIQUE_ID_SUFFIX_CONNECTED = "connected"
UNIQUE_ID_SUFFIXES = (
    UNIQUE_ID_SUFFIX_VPN_UID,
    UNIQUE_ID_SUFFIX_CONNECTED,
    UNIQUE_ID_SUFFIX_STATUS,
    UNIQUE_ID_SUFFIX_SWITCH,
    UNIQUE_ID_SUFFIX_UID,
)

OPTIONS_ACTION_CONFIGURE = "configure"
OPTIONS_ACTION_CLEANUP = "cleanup"
OPTIONS_ACTION_REPAIR_ENTITY_IDS = "repair_entity_ids"
SERVICE_REMOVE_UNAVAILABLE_ENTITIES = "remove_unavailable_entities"
SERVICE_REPAIR_ENTITY_ID_SUFFIXES = "repair_entity_id_suffixes"
CONF_CONFIG_ENTRY_ID = "config_entry_id"

LOG_MSG_VPN_CONNECTIONS_REMOVED = (
    "VPN connection(s) no longer available on the %s; related entities will show as unavailable: %s"
)
LOG_MSG_VPN_CONNECTIONS_REMOVED_HINT = (
    "You can remove obsolete entities under Settings > Devices & Services > Entities (filter by Fritz!Box VPN)."
)

MANUFACTURER_AVM = "AVM"
MODEL_FRITZBOX = "Fritz!Box"
MODEL_WIREGUARD_VPN = "WireGuard VPN"
INTEGRATION_TITLE = "Fritz!Box VPN"
NOTIFICATION_TITLE_AUTH_ERROR = "Fritz!Box VPN: Authentifizierungsfehler"

ERROR_KEY_UNKNOWN = "unknown"
ERROR_KEY_CANNOT_CONNECT = "cannot_connect"
ERROR_KEY_INVALID_AUTH = "invalid_auth"
ERROR_KEY_INVALID_HOST = "invalid_host"
ERROR_KEY_CONFIG_ENTRY_NOT_FOUND = "config_entry_not_found"

CONFIG_URL_INTEGRATIONS = "/config/integrations"


def auth_error_notification_id(host: str) -> str:
    """Return the persistent notification ID for auth errors."""
    return f"{DOMAIN}_auth_error_{host or HOST_FALLBACK_UNKNOWN}"


def host_from_config(config: Mapping[str, Any]) -> str:
    """Host from config/entry data; HOST_FALLBACK_UNKNOWN if missing."""
    return config.get(CONF_HOST, HOST_FALLBACK_UNKNOWN)


def mask_config_for_log(data: dict) -> dict:
    """Return a copy of the config dict with sensitive keys masked."""
    return {k: "***" if k in SENSITIVE_CONFIG_KEYS else v for k, v in data.items()}


def password_from_source(source: Mapping[str, Any] | None) -> str:
    """Return password from one dict (CONF_PASSWORD, 'password', or 'pass'), or empty string."""
    if not source:
        return ""
    return str(source.get(CONF_PASSWORD) or source.get("password") or source.get("pass") or "")


def password_from_sources(*sources: Mapping[str, Any] | None) -> str:
    """Return first non-empty password from any of the given dicts."""
    for src in sources:
        p = password_from_source(src)
        if p:
            return p
    return ""


STATUS_CONNECTED = "connected"
STATUS_ENABLED = "enabled"
STATUS_DISABLED = "disabled"
STATUS_UNKNOWN = "unknown"

VPN_STATUS_OPTIONS = (
    STATUS_CONNECTED,
    STATUS_ENABLED,
    STATUS_DISABLED,
    STATUS_UNKNOWN,
)

FRITZBOX_SSDP_INDICATORS = (
    "fritz.box",
    "fritzbox",
    "fritz!box",
    "avm",
    "fritz",
)

FRITZ_INTEGRATION_DOMAINS = ("fritz", "fritzbox_tools", "fritzbox", "fritzbox_tools_plus")
SENSITIVE_CONFIG_KEYS = ("password", "pass", "username", "user")

REPEATER_INDICATORS = (
    "repeater",
    "wlan repeater",
    "fritz!wlan repeater",
    "fritz!wlanrepeater",
)

ERROR_INDICATOR_AUTH = ("login failed", "invalid sid")
ERROR_INDICATOR_CONNECT = ("failed to get login page", "connection")
AUTH_INDICATORS = (
    "login failed",
    "invalid sid",
    "authentication failed",
    "invalid credentials",
    "unauthorized",
    "access denied",
)
