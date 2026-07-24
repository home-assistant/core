"""Constants for the OneDrive for Business integration."""

from collections.abc import Callable
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "onedrive_for_business"
CONF_FOLDER_PATH: Final = "folder_path"
CONF_FOLDER_ID: Final = "folder_id"
CONF_TENANT_ID: Final = "tenant_id"


OAUTH2_AUTHORIZE: Final = (
    "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
)
OAUTH2_TOKEN: Final = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

OAUTH_SCOPES: Final = [
    "Files.ReadWrite.All",
    "offline_access",
    "openid",
]

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)
