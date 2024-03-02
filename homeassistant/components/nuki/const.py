"""Constants for Nuki."""
DOMAIN = "nuki"

# Attributes
ATTR_BATTERY_CRITICAL = "battery_critical"
ATTR_NUKI_ID = "nuki_id"
ATTR_ENABLE = "enable"
ATTR_UNLATCH = "unlatch"

# Defaults
DEFAULT_PORT = 8080
DEFAULT_TIMEOUT = 20

ERROR_STATES = (0, 254, 255)

# Encrypt token, instead of using a plaintext token
CONF_ENCRYPT_TOKEN = "encrypt_token"
