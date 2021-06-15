"""Constants for the Nobø Ecohub integration."""

DOMAIN = "nobo_hub"

CONF_SERIAL = "serial"
CONF_OVERRIDE_TYPE = "override_type"
CONF_OVERRIDE_TYPE_CONSTANT = "Constant"
CONF_OVERRIDE_TYPE_NOW = "Now"
# This must be a non-empty string guaranteed to not be a week profile name
CONF_WEEK_PROFILE_NONE = "-"

ATTR_TEMP_COMFORT_C = "temp_comfort_c"
ATTR_TEMP_ECO_C = "temp_eco_c"
ATTR_OVERRIDE_ALLOWED = "override_allowed"
ATTR_TARGET_TYPE = "target_type"
ATTR_TARGET_ID = "target_id"
