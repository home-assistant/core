"""Constants for the SFTPClient integration."""

from collections.abc import Callable

from homeassistant.util.hass_dict import HassKey

DOMAIN = "sftp_client"
CONF_BACKUP_PATH = "backup"
DEFAULT_BACKUP_PATH = "backup"

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)
