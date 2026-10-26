"""Constants for the Sky Hub integration."""

from homeassistant.const import Platform

DOMAIN = "sky_hub"

PLATFORMS = [Platform.DEVICE_TRACKER]

ISSUE_LEGACY_KNOWN_DEVICES = "legacy_known_devices"

DEFAULT_HOST = "192.168.1.254"
