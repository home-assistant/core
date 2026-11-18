"""Constants for the Seafile integration."""

from collections.abc import Callable
import logging

from homeassistant.util.hass_dict import HassKey

DOMAIN = "seafile"
LOGGER = logging.getLogger(__package__)

CONF_LIBRARIES = "libraries"
CONF_LIBRARY_ID = "library_id"
CONF_OTP = "otp"

SUBENTRY_TYPE_LIBRARY = "library"

CONF_BACKUP = "backup"
CONF_BACKUP_PATH = "backup_path"
DEFAULT_BACKUP_PATH = "/Home Assistant backups"

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)
