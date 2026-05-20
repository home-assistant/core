"""Constants for the FRITZ!Box Tools integration."""

from enum import StrEnum
from typing import Literal

from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzActionFailedError,
    FritzAuthorizationError,
    FritzConnectionException,
    FritzInternalError,
    FritzLookUpError,
    FritzSecurityError,
    FritzServiceError,
)
from requests.exceptions import ConnectionError

from homeassistant.const import Platform


class MeshRoles(StrEnum):
    """Available Mesh roles."""

    NONE = "none"
    MASTER = "master"
    SLAVE = "slave"


DOMAIN = "fritz"
SCAN_INTERVAL = 30

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.IMAGE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

CONF_OLD_DISCOVERY = "old_discovery"
DEFAULT_CONF_OLD_DISCOVERY = False

CONF_FEATURE_DEVICE_TRACKING = "feature_device_tracking"
DEFAULT_CONF_FEATURE_DEVICE_TRACKING = True

CONF_FEATURE_WIREGUARD_VPN = "feature_wireguard_vpn"
DEFAULT_CONF_FEATURE_WIREGUARD_VPN = True

VPN_UNIQUE_ID_SUFFIX_SWITCH = "wireguard_vpn"
VPN_MODEL_WIREGUARD = "WireGuard VPN"
VPN_RETRY_AFTER_SECONDS = 300

VPN_STATUS_CONNECTED = "connected"
VPN_STATUS_ENABLED = "enabled"
VPN_STATUS_DISABLED = "disabled"
VPN_STATUS_UNKNOWN = "unknown"

VPN_AUTH_INDICATORS = (
    "login failed",
    "invalid sid",
    "authentication failed",
    "invalid credentials",
    "unauthorized",
    "access denied",
)

LOG_MSG_VPN_CONNECTIONS_REMOVED = "WireGuard VPN connection(s) removed: %s"

DSL_CONNECTION: Literal["dsl"] = "dsl"

DEFAULT_DEVICE_NAME = "Unknown device"
DEFAULT_HOST = "192.168.178.1"
DEFAULT_HTTP_PORT = 49000
DEFAULT_HTTPS_PORT = 49443
DEFAULT_USERNAME = ""
DEFAULT_SSL = False

ERROR_AUTH_INVALID = "invalid_auth"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UPNP_NOT_CONFIGURED = "upnp_not_configured"
ERROR_UNKNOWN = "unknown_error"

SWITCH_TYPE_DEFLECTION = "CallDeflection"
SWITCH_TYPE_PORTFORWARD = "PortForward"
SWITCH_TYPE_PROFILE = "Profile"
SWITCH_TYPE_WIFINETWORK = "WiFiNetwork"

BUTTON_TYPE_WOL = "WakeOnLan"

FRITZ_EXCEPTIONS = (
    ConnectionError,
    FritzActionError,
    FritzActionFailedError,
    FritzConnectionException,
    FritzInternalError,
    FritzServiceError,
    FritzLookUpError,
)

FRITZ_AUTH_EXCEPTIONS = (FritzAuthorizationError, FritzSecurityError)


CONNECTION_TYPE_LAN = "LAN"
