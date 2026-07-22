"""Constants for the OpenWrt (luci) integration."""

from homeassistant.const import Platform

DOMAIN = "luci"

PLATFORMS = [Platform.DEVICE_TRACKER]

DEFAULT_SSL = True
DEFAULT_VERIFY_SSL = False
