"""Constants for the SolarEdge Monitoring API."""

from datetime import timedelta
import logging

DOMAIN = "solaredge"

LOGGER = logging.getLogger(__package__)

DATA_API_CLIENT = "api_client"

# Config for solaredge monitoring api requests.
CONF_SITE_ID = "site_id"
DEFAULT_NAME = "SolarEdge"

OVERVIEW_UPDATE_DELAY = timedelta(minutes=15)
DETAILS_UPDATE_DELAY = timedelta(hours=12)
INVENTORY_UPDATE_DELAY = timedelta(hours=12)
POWER_FLOW_UPDATE_DELAY = timedelta(minutes=15)
ENERGY_DETAILS_DELAY = timedelta(minutes=15)

SCAN_INTERVAL = timedelta(minutes=15)
