"""Constants for the ZhongHong integration."""

from homeassistant.const import Platform

# Integration info
DOMAIN = "zhong_hong"
NAME = "ZhongHong HVAC"
MANUFACTURER = "ZhongHong"
MODEL = "HVAC Gateway"

# Platforms
PLATFORMS = [Platform.CLIMATE]

# Configuration
CONF_GATEWAY_ADDRESS = "gateway_address"
DEFAULT_PORT = 9999
DEFAULT_GATEWAY_ADDRESS = 1
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 5

# ZhongHong modes
ZHONG_HONG_MODE_COOL = "cool"
ZHONG_HONG_MODE_HEAT = "heat"
ZHONG_HONG_MODE_DRY = "dry"
ZHONG_HONG_MODE_FAN_ONLY = "fan_only"
