"""Constants for the Dropbox integration."""

from collections.abc import Callable

from homeassistant.util.hass_dict import HassKey

DOMAIN = "dropbox"

OAUTH2_AUTHORIZE = "https://www.dropbox.com/oauth2/authorize"
OAUTH2_TOKEN = "https://api.dropboxapi.com/oauth2/token"
OAUTH2_SCOPES = [
    "account_info.read",
    "files.content.read",
    "files.content.write",
    "files.metadata.read",
    "files.metadata.write",
]

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)
