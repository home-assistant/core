"""Constants for the PECO Outage Counter integration."""
import logging

DOMAIN = "peco"
LOGGER = logging.getLogger(__package__)
COUNTY_LIST = [
    "BUCKS",
    "CHESTER",
    "DELAWARE",
    "MONTGOMERY",
    "PHILADELPHIA",
    "YORK",
    "TOTAL",
]
SCAN_INTERVAL = 5
