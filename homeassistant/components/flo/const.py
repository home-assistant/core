"""Constants for the flo integration."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "flo"
CONF_USE_SSO = "use_sso"
FLO_HOME = "home"
FLO_AWAY = "away"
FLO_SLEEP = "sleep"
FLO_MODES = [FLO_HOME, FLO_AWAY, FLO_SLEEP]
