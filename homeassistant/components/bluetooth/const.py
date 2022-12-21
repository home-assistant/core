"""Constants for the Bluetooth integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN = "bluetooth"

CONF_ADAPTER = "adapter"
CONF_DETAILS = "details"
CONF_PASSIVE = "passive"


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

# The maximum time between advertisements for a device to be considered
# stale when the advertisement tracker can determine the interval for
# connectable devices.
#
# BlueZ uses 180 seconds by default but we give it a bit more time
# to account for the esp32's bluetooth stack being a bit slower
# than BlueZ's.
CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS: Final = 195


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


# When the linux kernel is configured with
# CONFIG_FW_LOADER_USER_HELPER_FALLBACK it
# can take up to 120s before the USB device
# is available if the firmware files
# are not present
LINUX_FIRMWARE_LOAD_FALLBACK_SECONDS = 120
BLUETOOTH_DISCOVERY_COOLDOWN_SECONDS = 5
