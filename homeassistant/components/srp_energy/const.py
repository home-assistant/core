"""Constants for the SRP Energy integration."""
from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "srp_energy"
DEFAULT_NAME = "Home"

CONF_IS_TOU = "is_tou"

PHOENIX_TIME_ZONE = "America/Phoenix"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1440)

DEVICE_CONFIG_URL = "https://www.srpnet.com/"
DEVICE_MANUFACTURER = "srpnet.com"
DEVICE_MODEL = "Service Api"
