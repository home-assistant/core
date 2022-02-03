"""Constants for the PECO Outage Counter integration."""
import logging

DOMAIN = "peco"
_LOGGER = logging.getLogger(__name__)
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
