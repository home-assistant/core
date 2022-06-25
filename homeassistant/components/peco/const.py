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
CONFIG_FLOW_COUNTIES: Final = [{county: county.capitalize()} for county in COUNTY_LIST]
SCAN_INTERVAL: Final = 9
CONF_COUNTY: Final = "county"
ATTR_CONTENT: Final = "content"
