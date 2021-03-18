"""Constants for the SRP Energy integration."""
from datetime import timedelta

SRP_ENERGY_DOMAIN = "srp_energy"
DEFAULT_NAME = "SRP Energy"

CONF_IS_TOU = "is_tou"

ATTRIBUTION = "Powered by SRP Energy"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1440)

SENSOR_NAME = "Usage"
SENSOR_TYPE = "usage"

ICON = "mdi:flash"
