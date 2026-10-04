"""Constants for the ENGIE Belgium integration."""

from datetime import timedelta
import logging

DOMAIN = "engie_be"
ATTRIBUTION = "Data provided by ENGIE Belgium"

LOGGER = logging.getLogger(__package__)

CONF_MFA_METHOD = "mfa_method"
CONF_REFRESH_TOKEN = "refresh_token"

SERVICE_GET_EPEX_PRICES_FOR_DATE = "get_epex_prices_for_date"

USER_MANAGEMENT_URL = (
    "https://www.engie.be/nl/energiedesk/usermanagement/manage-access/"
)

CONTRACTS_RETRY_INTERVAL = timedelta(minutes=5)

PRICES_SCAN_INTERVAL = timedelta(hours=1)
EPEX_SCAN_INTERVAL = timedelta(hours=1)
