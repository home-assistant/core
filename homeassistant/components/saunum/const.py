"""Constants for the Saunum Leil Sauna Control Unit integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "saunum"

# Device information
DEVICE_NAME: Final = "Saunum Leil"
DEVICE_MANUFACTURER: Final = "Saunum"
DEVICE_MODEL: Final = "Leil Touch Panel"

# Scan intervals
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=60)
DELAYED_REFRESH_SECONDS: Final = timedelta(seconds=3)

# Option keys for preset names
OPT_PRESET_NAME_TYPE_1: Final = "preset_name_type_1"
OPT_PRESET_NAME_TYPE_2: Final = "preset_name_type_2"
OPT_PRESET_NAME_TYPE_3: Final = "preset_name_type_3"

# Default preset names (translation keys)
DEFAULT_PRESET_NAME_TYPE_1: Final = "type_1"
DEFAULT_PRESET_NAME_TYPE_2: Final = "type_2"
DEFAULT_PRESET_NAME_TYPE_3: Final = "type_3"
