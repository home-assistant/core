"""Constants for decora_wifi."""
DOMAIN = "decora_wifi"

CONF_FAN = "fan"
CONF_LIGHT = "light"
CONF_OPTIONS = "options"
CONF_TITLE = "myLeviton Decora Wifi"

DEFAULT_SCAN_INTERVAL = 120

MODELS_FAN = ["DW4SF"]

SPEEDS_FAN = {"DW4SF": 4}

PLATFORMS = [CONF_LIGHT, CONF_FAN]
