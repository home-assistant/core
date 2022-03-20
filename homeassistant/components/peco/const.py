"""Constants for the PECO Outage Counter integration."""
import logging
from typing import Final

DOMAIN: Final = "peco"
LOGGER: Final = logging.getLogger(__package__)
COUNTY_LIST: Final = [
    "BUCKS",
    "CHESTER",
    "DELAWARE",
    "MONTGOMERY",
    "PHILADELPHIA",
    "YORK",
    "TOTAL",
]
SCAN_INTERVAL: Final = 1
CONF_COUNTY: Final = "county"
