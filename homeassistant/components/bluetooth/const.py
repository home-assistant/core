"""Constants for the Bluetooth integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final, TypedDict

DOMAIN = "bluetooth"

CONF_ADAPTER = "adapter"
CONF_DETAILS = "details"
CONF_PASSIVE = "passive"

WINDOWS_DEFAULT_BLUETOOTH_ADAPTER = "bluetooth"
MACOS_DEFAULT_BLUETOOTH_ADAPTER = "Core Bluetooth"
UNIX_DEFAULT_BLUETOOTH_ADAPTER = "hci0"

DEFAULT_ADAPTER_BY_PLATFORM = {
    "Windows": WINDOWS_DEFAULT_BLUETOOTH_ADAPTER,
    "Darwin": MACOS_DEFAULT_BLUETOOTH_ADAPTER,
}


# Some operating systems hide the adapter address for privacy reasons (ex MacOS)
DEFAULT_ADDRESS: Final = "00:00:00:00:00:00"

SOURCE_LOCAL: Final = "local"

DATA_MANAGER: Final = "bluetooth_manager"

UNAVAILABLE_TRACK_SECONDS: Final = 60 * 5

START_TIMEOUT = 15

# The maximum time between advertisements for a device to be considered
# stale when the advertisement tracker cannot determine the interval.
#
# We have to set this quite high as we don't know
# when devices fall out of the ESPHome device (and other non-local scanners)'s
# stack like we do with BlueZ so its safer to assume its available
# since if it does go out of range and it is in range
# of another device the timeout is much shorter and it will
# switch over to using that adapter anyways.
#
FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS: Final = 60 * 15


# We must recover before we hit the 180s mark
# where the device is removed from the stack
# or the devices will go unavailable. Since
# we only check every 30s, we need this number
# to be
# 180s Time when device is removed from stack
# - 30s check interval
# - 30s scanner restart time * 2
#
SCANNER_WATCHDOG_TIMEOUT: Final = 90
# How often to check if the scanner has reached
# the SCANNER_WATCHDOG_TIMEOUT without seeing anything
SCANNER_WATCHDOG_INTERVAL: Final = timedelta(seconds=30)


class AdapterDetails(TypedDict, total=False):
    """Adapter details."""

    address: str
    sw_version: str
    hw_version: str | None
    passive_scan: bool


ADAPTER_ADDRESS: Final = "address"
ADAPTER_SW_VERSION: Final = "sw_version"
ADAPTER_HW_VERSION: Final = "hw_version"
ADAPTER_PASSIVE_SCAN: Final = "passive_scan"
