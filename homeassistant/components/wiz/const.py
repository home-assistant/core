"""Constants for the WiZ Platform integration."""

from datetime import timedelta
from pywizlight.bulb import PIR_SOURCE

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
OCCUPANCY_SOURCES = frozenset({PIR_SOURCE, "wfsens"})
# NOTE: When adding to OCCUPANCY_SOURCES (e.g., "wfsens"), ensure tests cover push updates with these sources.
#       See: tests/components/wiz/test_xxx.py. Verify that entity creation and update for src="wfsens" behaves the same as for src="pir".
