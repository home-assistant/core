"""Constants for the Nobø Ecohub integration."""

from typing import Final

DOMAIN = "nobo_hub"

CONF_SERIAL = "serial"
CONF_OVERRIDE_TYPE = "override_type"
OVERRIDE_TYPE_CONSTANT = "constant"
OVERRIDE_TYPE_NOW = "now"

NOBO_MANUFACTURER = "Glen Dimplex Nordic AS"
ATTR_HARDWARE_VERSION: Final = "hardware_version"
ATTR_SOFTWARE_VERSION: Final = "software_version"
ATTR_SERIAL: Final = "serial"
ATTR_TEMP_COMFORT_C: Final = "temp_comfort_c"
ATTR_TEMP_ECO_C: Final = "temp_eco_c"
ATTR_ZONE_ID: Final = "zone_id"
