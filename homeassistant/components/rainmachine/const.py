"""Define constants for the SimpliSafe component."""
from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "rainmachine"

DATA_CLIENT = "client"

DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_SSL = True

PROVISION_SETTINGS = "provision.settings"
RESTRICTIONS_CURRENT = "restrictions.current"
RESTRICTIONS_UNIVERSAL = "restrictions.universal"

TOPIC_UPDATE = "update_{0}"
