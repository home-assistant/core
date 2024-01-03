"""Constants for UPC Connect."""
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "upc_connect"

PLATFORMS: Final = [Platform.DEVICE_TRACKER]

UPC_CONNECT_TRACKED_DEVICES: Final = "upc_connect_tracked_devices"

TRACKER_SCAN_INTERVAL: Final = 120
