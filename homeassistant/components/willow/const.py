"""Constants for the Willow integration."""

from datetime import timedelta
import logging

DOMAIN = "willow"
LOGGER = logging.getLogger(__package__)
MANUFACTURER = "PW Willow Pty Ltd"
SCAN_INTERVAL = timedelta(minutes=15)

OAUTH2_AUTHORIZE = "https://api.plantwithwillow.com.au/oauth/authorize/"
OAUTH2_TOKEN = "https://api.plantwithwillow.com.au/oauth/token/"
OAUTH2_CLIENT_ID = "ea4a4aed-9de2-4dd3-bbe4-7ef657cffdda"
OAUTH2_CLIENT_SECRET = (
    "df58fd78e62310b77be94290788d1439766982b0056928d5d26b3a3c526dded2"
)
