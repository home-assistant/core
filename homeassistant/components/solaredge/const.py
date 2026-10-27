"""Constants for the SolarEdge Monitoring API."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN = "solaredge"

LOGGER = logging.getLogger(__package__)

DATA_API_CLIENT: Final = "api_client"
DATA_MODULES_COORDINATOR: Final = "modules_coordinator"

API_BASE_URL = "https://monitoringapi.solaredge.com/v2"
OAUTH2_AUTHORIZE = "https://connect.solaredge.com/authorize"
OAUTH2_TOKEN = f"{API_BASE_URL}/oauth2/token"
OAUTH2_CALLBACK_PATH = "/api/solaredge/oauth/callback"

CONF_SITE_ID = "site_id"
CONF_SECTION_WEB_AUTH = "web_auth"
DEFAULT_NAME = "SolarEdge"

OVERVIEW_UPDATE_DELAY = timedelta(hours=1)
DETAILS_UPDATE_DELAY = timedelta(hours=24)
INVENTORY_UPDATE_DELAY = timedelta(hours=24)
POWER_FLOW_UPDATE_DELAY = timedelta(hours=1)
ENERGY_DETAILS_DELAY = timedelta(hours=1)
STORAGE_DATA_UPDATE_DELAY = timedelta(hours=4)
MODULE_STATISTICS_UPDATE_DELAY = timedelta(hours=12)

SCAN_INTERVAL = timedelta(hours=1)
