"""Constants for the Bluetooth integration."""

from __future__ import annotations

from typing import Final

from habluetooth import (  # noqa: F401
    CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    SCANNER_WATCHDOG_INTERVAL,
    SCANNER_WATCHDOG_TIMEOUT,
)

DOMAIN = "bluetooth"

CONF_ADAPTER = "adapter"
CONF_DETAILS = "details"
CONF_PASSIVE = "passive"


CONF_SOURCE: Final = "source"
CONF_SOURCE_DOMAIN: Final = "source_domain"
CONF_SOURCE_MODEL: Final = "source_model"
CONF_SOURCE_CONFIG_ENTRY_ID: Final = "source_config_entry_id"
CONF_SOURCE_DEVICE_ID: Final = "source_device_id"

SOURCE_LOCAL: Final = "local"

DATA_MANAGER: Final = "bluetooth_manager"

UNAVAILABLE_TRACK_SECONDS: Final = 60 * 5

START_TIMEOUT = 15


# When the linux kernel is configured with
# CONFIG_FW_LOADER_USER_HELPER_FALLBACK it
# can take up to 120s before the USB device
# is available if the firmware files
# are not present
LINUX_FIRMWARE_LOAD_FALLBACK_SECONDS = 120
BLUETOOTH_DISCOVERY_COOLDOWN_SECONDS = 5
