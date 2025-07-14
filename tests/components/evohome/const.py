"""Constants for the evohome tests."""

from __future__ import annotations

from typing import Final

ACCESS_TOKEN: Final = "at_1dc7z657UKzbhKA..."
REFRESH_TOKEN: Final = "rf_jg68ZCKYdxEI3fF..."
SESSION_ID: Final = "F7181186..."
USERNAME: Final = "test_user@gmail.com"

# The h-numbers refer to issues in HA's core repo
TEST_INSTALLS: Final = (
    "minimal",  # evohome: single zone, no DHW
    "default",  # evohome: multi-zone, with DHW
    "h032585",  # VisionProWifi: no preset modes for TCS, zoneId=systemId
    "h099625",  # RoundThermostat
    "h139906",  # zone with null schedule
    "sys_004",  # RoundModulation
)
#   "botched",  # as default: but with activeFaults, ghost zones & unknown types

TEST_INSTALLS_WITH_DHW: Final = ("default", "botched")
