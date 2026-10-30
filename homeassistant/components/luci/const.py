"""Constants for the OpenWrt (luci) integration."""

from homeassistant.const import Platform

DOMAIN = "luci"

PLATFORMS = [Platform.DEVICE_TRACKER]

ISSUE_LEGACY_KNOWN_DEVICES = "legacy_known_devices"

DEFAULT_SSL = True
DEFAULT_VERIFY_SSL = False
