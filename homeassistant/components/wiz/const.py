"""Constants for the WiZ Platform integration."""

from datetime import timedelta

from pywizlight.exceptions import (
    WizLightConnectionError,
    WizLightNotKnownBulb,
    WizLightTimeOutError,
)

DOMAIN = "wiz"
DEFAULT_NAME = "WiZ"

DISCOVER_SCAN_TIMEOUT = 10
DISCOVERY_INTERVAL = timedelta(minutes=15)

WIZ_EXCEPTIONS = (
    OSError,
    WizLightTimeOutError,
    TimeoutError,
    WizLightConnectionError,
    ConnectionRefusedError,
)
WIZ_CONNECT_EXCEPTIONS = (WizLightNotKnownBulb, *WIZ_EXCEPTIONS)

SIGNAL_WIZ_PIR = "wiz_pir_{}"
