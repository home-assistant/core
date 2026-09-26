"""Constants for the ENGIE Belgium integration."""

from datetime import timedelta
import logging

DOMAIN = "engie_be"
ATTRIBUTION = "Data provided by ENGIE Belgium"

LOGGER = logging.getLogger(__package__)

CONF_MFA_METHOD = "mfa_method"
CONF_REFRESH_TOKEN = "refresh_token"

USER_MANAGEMENT_URL = (
    "https://www.engie.be/nl/energiedesk/usermanagement/manage-access/"
)

PRICES_SCAN_INTERVAL = timedelta(hours=1)
