"""Constants for the Bluetooth integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final, TypedDict

DOMAIN = "bluetooth"

CONF_ADAPTER = "adapter"
CONF_DETAILS = "details"

WINDOWS_DEFAULT_BLUETOOTH_ADAPTER = "bluetooth"
MACOS_DEFAULT_BLUETOOTH_ADAPTER = "Core Bluetooth"
UNIX_DEFAULT_BLUETOOTH_ADAPTER = "hci0"

DEFAULT_ADAPTERS = {MACOS_DEFAULT_BLUETOOTH_ADAPTER, UNIX_DEFAULT_BLUETOOTH_ADAPTER}

DEFAULT_ADAPTER_BY_PLATFORM = {
    "Windows": WINDOWS_DEFAULT_BLUETOOTH_ADAPTER,
    "Darwin": MACOS_DEFAULT_BLUETOOTH_ADAPTER,
}

# Some operating systems hide the adapter address for privacy reasons (ex MacOS)
DEFAULT_ADDRESS: Final = "00:00:00:00:00:00"

SOURCE_LOCAL: Final = "local"

DATA_MANAGER: Final = "bluetooth_manager"

UNAVAILABLE_TRACK_SECONDS: Final = 60 * 5
START_TIMEOUT = 12
SCANNER_WATCHDOG_TIMEOUT: Final = 60 * 5
SCANNER_WATCHDOG_INTERVAL: Final = timedelta(seconds=SCANNER_WATCHDOG_TIMEOUT)


class AdapterDetails(TypedDict, total=False):
    """Adapter details."""

    address: str
    sw_version: str
    hw_version: str


ADAPTER_ADDRESS: Final = "address"
ADAPTER_SW_VERSION: Final = "sw_version"
ADAPTER_HW_VERSION: Final = "hw_version"
