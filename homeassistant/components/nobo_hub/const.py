"""Constants for the Nobø Ecohub integration."""

DOMAIN = "nobo_hub"

CONF_SERIAL = "serial"
CONF_OVERRIDE_TYPE = "override_type"
OVERRIDE_TYPE_CONSTANT = "constant"
OVERRIDE_TYPE_NOW = "now"

# Hub serial: 9-digit batch prefix + 3-digit per-hub suffix. Discovery
# broadcasts only the prefix; the user supplies the suffix.
SERIAL_PREFIX_LENGTH = 9
SERIAL_LENGTH = SERIAL_PREFIX_LENGTH + 3

NOBO_MANUFACTURER = "Glen Dimplex Nordic AS"
ATTR_HARDWARE_VERSION = "hardware_version"
ATTR_SOFTWARE_VERSION = "software_version"
ATTR_SERIAL = "serial"
ATTR_TEMP_COMFORT_C = "temp_comfort_c"
ATTR_TEMP_ECO_C = "temp_eco_c"
ATTR_ZONE_ID = "zone_id"
