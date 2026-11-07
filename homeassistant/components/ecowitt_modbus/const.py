"""Constants for the Ecowitt Modbus integration."""

from ecowitt_modbus import SUPPORTED_MODELS

DOMAIN = "ecowitt_modbus"

# Selector options have to be lowercase slugs, but the library keys its
# models by the name printed on the device, which is what gets stored in the
# config entry and shown to the user.
MODEL_OPTIONS: dict[str, str] = {name.lower(): name for name in SUPPORTED_MODELS}

CONF_UNIT_ID = "unit_id"

DEFAULT_PORT = 502

# Modbus RTU device addresses run 1-247; 248-252 are reserved. These sensors
# accept up to 252 in their own address register, but an address above 247
# cannot be reached over the wire.
MAX_UNIT_ID = 247
