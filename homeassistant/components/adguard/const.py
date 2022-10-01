"""Constants for the AdGuard Home integration."""
import logging

DOMAIN = "adguard"

LOGGER = logging.getLogger(__package__)

DATA_ADGUARD_CLIENT = "adguard_client"
DATA_ADGUARD_VERSION = "adguard_version"

CONF_FORCE = "force"

SERVICE_ADD_ALLOW_URL = "add_allow_url"
SERVICE_ADD_BLOCK_URL = "add_block_url"
SERVICE_DISABLE_URL = "disable_url"
SERVICE_ENABLE_URL = "enable_url"
SERVICE_REFRESH = "refresh"
SERVICE_REMOVE_ALLOW_URL = "remove_allow_url"
SERVICE_REMOVE_BLOCK_URL = "remove_block_url"
