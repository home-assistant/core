"""Shared constants for the Aquarite integration."""

DOMAIN = "aquarite"
BRAND = "Hayward"
MODEL = "Aquarite"

PATH_PREFIX = "main."
PATH_HASCD = f"{PATH_PREFIX}hasCD"
PATH_HASCL = f"{PATH_PREFIX}hasCL"
PATH_HASPH = f"{PATH_PREFIX}hasPH"
PATH_HASRX = f"{PATH_PREFIX}hasRX"
PATH_HASUV = f"{PATH_PREFIX}hasUV"
PATH_HASHIDRO = f"{PATH_PREFIX}hasHidro"
PATH_HASLED = f"{PATH_PREFIX}hasLED"

# Time intervals (seconds)
DEFAULT_HEALTH_CHECK_INTERVAL = 300  # 5 minutes
LED_PULSE_DELAY = 1.5  # Delay between off and on when cycling LED color

# Options flow keys
CONF_HEALTH_CHECK_INTERVAL = "health_check_interval"
