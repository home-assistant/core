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

from homeassistant.const import Platform


class MeshRoles(StrEnum):
    """Available Mesh roles."""

    NONE = "none"
    MASTER = "master"
    SLAVE = "slave"


DOMAIN = "fritz"

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

DATA_FRITZ = "fritz_data"

DSL_CONNECTION: Literal["dsl"] = "dsl"

DEFAULT_DEVICE_NAME = "Unknown device"
DEFAULT_HOST = "192.168.178.1"
DEFAULT_PORT = 49000
DEFAULT_USERNAME = ""

ERROR_AUTH_INVALID = "invalid_auth"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UPNP_NOT_CONFIGURED = "upnp_not_configured"
ERROR_UNKNOWN = "unknown_error"

FRITZ_SERVICES = "fritz_services"
SERVICE_REBOOT = "reboot"
SERVICE_RECONNECT = "reconnect"
SERVICE_CLEANUP = "cleanup"
SERVICE_SET_GUEST_WIFI_PW = "set_guest_wifi_password"

SWITCH_TYPE_DEFLECTION = "CallDeflection"
SWITCH_TYPE_PORTFORWARD = "PortForward"
SWITCH_TYPE_PROFILE = "Profile"
SWITCH_TYPE_WIFINETWORK = "WiFiNetwork"

UPTIME_DEVIATION = 5

FRITZ_EXCEPTIONS = (
    FritzActionError,
    FritzActionFailedError,
    FritzConnectionException,
    FritzInternalError,
    FritzServiceError,
    FritzLookUpError,
)

FRITZ_AUTH_EXCEPTIONS = (FritzAuthorizationError, FritzSecurityError)

WIFI_STANDARD = {1: "2.4Ghz", 2: "5Ghz", 3: "5Ghz", 4: "Guest"}
