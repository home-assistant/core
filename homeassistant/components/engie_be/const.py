"""Constants for the ENGIE Belgium integration."""

from datetime import timedelta
import logging

from homeassistant.util.signal_type import SignalTypeFormat

DOMAIN = "engie_be"
ATTRIBUTION = "Data provided by ENGIE Belgium"

LOGGER = logging.getLogger(__package__)

CONF_MFA_METHOD = "mfa_method"
CONF_REFRESH_TOKEN = "refresh_token"

USER_MANAGEMENT_URL = (
    "https://www.engie.be/nl/energiedesk/usermanagement/manage-access/"
)

CONTRACTS_RETRY_INTERVAL = timedelta(minutes=5)

RELATIONS_SCAN_INTERVAL = timedelta(hours=1)
PRICES_SCAN_INTERVAL = timedelta(hours=1)
EPEX_SCAN_INTERVAL = timedelta(hours=1)
PEAKS_SCAN_INTERVAL = timedelta(hours=1)

NEW_HOUSEHOLDS_SIGNAL: SignalTypeFormat[set[str]] = SignalTypeFormat(
    f"{DOMAIN}_new_households_{{}}"
)
REMOVED_HOUSEHOLDS_SIGNAL: SignalTypeFormat[set[str]] = SignalTypeFormat(
    f"{DOMAIN}_removed_households_{{}}"
)
