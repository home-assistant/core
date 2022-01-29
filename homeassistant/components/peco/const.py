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
API_URL = "https://kubra.io/data/e574164b-add3-4f4a-9b52-22aff7a96064/public/reports/a36a6292-1c55-44de-a6a9-44fedf9482ee_report.json"
SCAN_INTERVAL = 5
