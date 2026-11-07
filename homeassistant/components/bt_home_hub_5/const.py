"""Constants for the BT Home Hub 5 integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "bt_home_hub_5"
DEFAULT_HOST = "192.168.1.254"
SCAN_INTERVAL = timedelta(seconds=10)
PLATFORMS = [Platform.DEVICE_TRACKER]

ISSUE_LEGACY_KNOWN_DEVICES = "legacy_known_devices"
