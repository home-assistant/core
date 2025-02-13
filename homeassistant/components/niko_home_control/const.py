"""Constants for niko_home_control integration."""

import logging

DOMAIN = "niko_home_control"
_LOGGER = logging.getLogger(__name__)


NIKO_THERMOSTAT_MODES_MAP = {
    "off": 3,
    "cool": 4,
    "auto": 5,
}
