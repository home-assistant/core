"""Constants for the OpenWrt (luci) integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "luci"

PLATFORMS = [Platform.DEVICE_TRACKER]

DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

CONF_CONSIDER_HOME = "consider_home"
DEFAULT_CONSIDER_HOME = timedelta(seconds=180)
