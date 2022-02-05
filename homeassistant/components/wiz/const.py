"""Constants for the WiZ Platform integration."""
from datetime import timedelta

from pywizlight.exceptions import WizLightConnectionError, WizLightTimeOutError

DOMAIN = "wiz"
DEFAULT_NAME = "WiZ"

DISCOVER_SCAN_TIMEOUT = 10
DISCOVERY_INTERVAL = timedelta(minutes=15)

SOCKET_DEVICE_STR = "_SOCKET_"

WIZ_EXCEPTIONS = (
    OSError,
    WizLightTimeOutError,
    TimeoutError,
    WizLightConnectionError,
    ConnectionRefusedError,
)
