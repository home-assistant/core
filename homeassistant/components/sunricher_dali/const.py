"""Constants for the Sunricher DALI integration."""

from typing import Final

DOMAIN: Final = "sunricher_dali"
MANUFACTURER: Final = "Sunricher"
CONF_SERIAL_NUMBER: Final = "serial_number"

# Minimum gateway versions known to work correctly with this integration.
# See https://github.com/maginawin/ha-dali-center/issues/69 for the
# credential-decryption failure that motivated this baseline.
MIN_SUPPORTED_SW_VERSION: Final = "3.59"
MIN_SUPPORTED_FW_VERSION: Final = "1.45"
