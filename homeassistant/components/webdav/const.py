"""Constants for the WebDAV integration."""

from collections.abc import Callable
from enum import StrEnum

from homeassistant.util.hass_dict import HassKey

DOMAIN = "webdav"

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

CONF_BACKUP_PATH = "backup_path"


class WebDavService(StrEnum):
    """WebDAV actions."""

    UPLOAD = "upload"


class WebDavServiceArgument(StrEnum):
    """WebDAV action fields."""

    DESTINATION_FOLDER = "destination_folder"
    FILENAME = "filename"
