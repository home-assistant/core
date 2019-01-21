"""Define constants for the SimpliSafe component."""
import logging
from datetime import timedelta

LOGGER = logging.getLogger('homeassistant.components.rainmachine')

DOMAIN = 'rainmachine'

DATA_CLIENT = 'client'

DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_SSL = True

TOPIC_UPDATE = 'update_{0}'
