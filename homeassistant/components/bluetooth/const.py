"""Constants for the Bluetooth integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN = "bluetooth"
DEFAULT_NAME = "Bluetooth"

CONF_ADAPTER = "adapter"

MACOS_DEFAULT_BLUETOOTH_ADAPTER = "CoreBluetooth"
UNIX_DEFAULT_BLUETOOTH_ADAPTER = "hci0"

DEFAULT_ADAPTERS = {MACOS_DEFAULT_BLUETOOTH_ADAPTER, UNIX_DEFAULT_BLUETOOTH_ADAPTER}

SOURCE_LOCAL: Final = "local"

DATA_MANAGER: Final = "bluetooth_manager"

UNAVAILABLE_TRACK_SECONDS: Final = 60 * 5
START_TIMEOUT = 12
SCANNER_WATCHDOG_TIMEOUT: Final = 60 * 5
SCANNER_WATCHDOG_INTERVAL: Final = timedelta(seconds=SCANNER_WATCHDOG_TIMEOUT)
