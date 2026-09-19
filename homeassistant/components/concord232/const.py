"""Constants for the Concord232 integration."""

from typing import Final

DOMAIN: Final = "concord232"

DEFAULT_PORT: Final = 5007
DEFAULT_MODE: Final = "audible"

MODE_AUDIBLE: Final = "audible"
MODE_SILENT: Final = "silent"

DATA_IMPORT_LOCK: Final = f"{DOMAIN}_import_lock"

CONF_EXCLUDE_ZONES: Final = "exclude_zones"
CONF_ZONE_TYPES: Final = "zone_types"

CONF_IMPORT_PLATFORM: Final = "import_platform"
CONF_IMPORTED_PLATFORMS: Final = "imported_platforms"
