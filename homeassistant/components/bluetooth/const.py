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

MAX_DBUS_SETUP_SECONDS = 5

# Anything after 30s is considered stale, we have buffer
# for start timeouts and execution time
STALE_ADVERTISEMENT_SECONDS: Final = 30 + START_TIMEOUT + MAX_DBUS_SETUP_SECONDS


# We must recover before we hit the 180s mark
# where the device is removed from the stack
# or the devices will go unavailable. Since
# we only check every 30s, we need this number
# to be
# 180s Time when device is removed from stack
# - 30s check interval
# - 20s scanner restart time * 2
#
SCANNER_WATCHDOG_TIMEOUT: Final = 110
# How often to check if the scanner has reached
# the SCANNER_WATCHDOG_TIMEOUT without seeing anything
SCANNER_WATCHDOG_INTERVAL: Final = timedelta(seconds=30)


class AdapterDetails(TypedDict, total=False):
    """Adapter details."""

    address: str
    sw_version: str
    hw_version: str
    passive_scan: bool


ADAPTER_ADDRESS: Final = "address"
ADAPTER_SW_VERSION: Final = "sw_version"
ADAPTER_HW_VERSION: Final = "hw_version"
ADAPTER_PASSIVE_SCAN: Final = "passive_scan"
