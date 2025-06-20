"""Constants for the OneDrive integration."""

from collections.abc import Callable
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "onedrive"
CONF_FOLDER_NAME: Final = "folder_name"
CONF_FOLDER_ID: Final = "folder_id"

CONF_DELETE_PERMANENTLY: Final = "delete_permanently"

# replace "consumers" with "common", when adding SharePoint or OneDrive for Business support
OAUTH2_AUTHORIZE: Final = (
    "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
)
OAUTH2_TOKEN: Final = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"

OAUTH_SCOPES: Final = [
    "Files.ReadWrite.AppFolder",
    "offline_access",
    "openid",
]

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)
