"""Constants for the Willow integration."""

from datetime import timedelta
import logging

DOMAIN = "willow"
LOGGER = logging.getLogger(__package__)
MANUFACTURER = "PW Willow Pty Ltd"
WILLOW_BASE_URL = "https://api.plantwithwillow.com.au"
SCAN_INTERVAL = timedelta(minutes=15)

OAUTH2_AUTHORIZE = f"{WILLOW_BASE_URL}/oauth/authorize/"
OAUTH2_TOKEN = f"{WILLOW_BASE_URL}/oauth/token/"
OAUTH2_CLIENT_ID = "ea4a4aed-9de2-4dd3-bbe4-7ef657cffdda"
OAUTH2_CLIENT_SECRET = (
    "df58fd78e62310b77be94290788d1439766982b0056928d5d26b3a3c526dded2"
)

GET_PROFILE_URL = f"{WILLOW_BASE_URL}/api/v1/profiles/short/"
GET_DEVICES_URL = f"{WILLOW_BASE_URL}/api/v1b/sensor/paired/"

PANEL_URL_PATH = "willow"
PANEL_TITLE = "Willow"
PANEL_ICON = "mdi:sprout"
PANEL_NAME = "willow-panel"
PANEL_STATIC_PATH = "/willow_panel"
PANEL_FILE = "willow-panel.js"
