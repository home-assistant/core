"""Constants for the flo integration."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "flo"
CONF_USE_SSO = "use_sso"
FLO_HOME = "home"
FLO_AWAY = "away"
FLO_SLEEP = "sleep"
FLO_MODES = [FLO_HOME, FLO_AWAY, FLO_SLEEP]

# Valves without a water-temperature sensor report a fixed placeholder instead of
# omitting tempF. No domestic supply reaches boiling, so a reading at or above
# this is a sentinel rather than a measurement.
IMPLAUSIBLE_WATER_TEMP_F = 212.0
