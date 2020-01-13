"""Constants used by vizio component."""
CONF_UNIQUE_ID = "unique_id"
CONF_VOLUME_STEP = "volume_step"

DEFAULT_NAME = "Vizio SmartCast"
DEFAULT_VOLUME_STEP = 1
DEFAULT_DEVICE_CLASS = "tv"
DEVICE_ID = "pyvizio"

DOMAIN = "vizio"

ICON = {"tv": "mdi:television", "soundbar": "mdi:speaker"}

UPDATE_OPTIONS_SIGNAL = f"{DOMAIN}_options_update"
