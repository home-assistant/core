"""Constants for the Panasonic Window A/C (Hong Kong/Macau) integration."""

DOMAIN = "panasonic_window_ac_hk"

DEVICE_NAME = "Panasonic Window AC (Hong Kong)"

CONF_INFRARED_EMITTER_ENTITY_ID = "infrared_emitter_entity_id"

# Default assumed state for a freshly added unit.
DEFAULT_MODE = "cool"
DEFAULT_TEMP = 24.0
DEFAULT_FAN = "auto"
DEFAULT_SWING = "auto"

# Fan speeds (must match the encoder's FAN_NIBBLE keys).
FAN_MODES = ["auto", "low", "mediumLow", "medium", "mediumHigh", "high"]
# Swing positions (must match the encoder's SWING_NIBBLE keys).
SWING_MODES = ["auto", "fixed"]
