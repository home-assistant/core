"""Constants for the OneDrive integration."""

from collections.abc import Callable
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "onedrive"

# replace "consumers" with "common", when adding SharePoint or OneDrive for Business support
OAUTH2_AUTHORIZE: Final = (
    "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
)
OAUTH2_TOKEN: Final = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"

OAUTH_SCOPES: Final = [
    "https://graph.microsoft.com/files.readwrite.AppFolder",
    "offline_access",
    "openid",
]

CONF_APPROOT_ID: Final = "approot_id"

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)
