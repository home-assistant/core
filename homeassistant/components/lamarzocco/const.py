"""Constants for the La Marzocco integration."""

from typing import Final

DOMAIN: Final = "lamarzocco"

CONF_USE_BLUETOOTH: Final = "use_bluetooth"
CONF_INSTALLATION_KEY: Final = "installation_key"
CONF_OFFLINE_MODE: Final = "offline_mode"

BT_MODEL_PREFIXES: Final = ("MICRA", "MINI", "LINEA", "GS3")

# never write these to logs or diagnostics
TO_REDACT: Final = {"serial_number", "ble_auth_token"}
