"""Constants for niko_home_control integration."""

import logging

DOMAIN = "niko_home_control"
_LOGGER = logging.getLogger(__name__)


NIKO_HOME_CONTROL_THERMOSTAT_MODES = {
    "OFF": 3,
    "cool": 4,
    "auto": 5,
}
