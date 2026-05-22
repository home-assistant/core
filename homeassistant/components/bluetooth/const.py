"""Constants for the Bluetooth integration."""

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


# pylint: disable-next=home-assistant-duplicate-const
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

# Defaults used when an ACTIVE-mode async_register_callback is made without
# explicit scan_interval / scan_duration values. The integration is expected
# to declare its actual cadence; these defaults exist so unmigrated callers
# still get on-demand active windows instead of continuous active scanning.
DEFAULT_ACTIVE_SCAN_INTERVAL: Final = 120.0  # 2 minutes
DEFAULT_ACTIVE_SCAN_DURATION: Final = 10.0
