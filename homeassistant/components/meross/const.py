"""Constants for the Meross Bluetooth integration."""

from logging import Logger, getLogger

DOMAIN = "meross"
MANUFACTURER = "Meross"
LOGGER: Logger = getLogger(__package__)

DEVICE_STARTUP_TIMEOUT = 30
# Local watchdog: mark unavailable if no parseable advertisement.
# Needed on macOS where Bleak's discovered cache often never expires, so HA's
# async_track_unavailable may never fire after battery removal / BT off.
ADVERTISEMENT_STALE_SECONDS = 600

MANUAL_SCAN_DURATION = 15
