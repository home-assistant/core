"""Constants for the huum integration."""

from homeassistant.const import Platform

DOMAIN = "huum"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.LIGHT, Platform.NUMBER]

CONFIG_STEAMER = 1
CONFIG_LIGHT = 2
CONFIG_STEAMER_AND_LIGHT = 3
