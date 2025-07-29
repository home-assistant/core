"""Constants for the Backblaze integration."""

from collections.abc import Callable
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "backblaze"

CONF_KEY_ID = "key_id"
CONF_APPLICATION_KEY = "application_key"
CONF_BUCKET = "bucket"
CONF_PREFIX = "prefix"

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

METADATA_FILE_SUFFIX = ".metadata.json"
METADATA_VERSION = "1"

BACKBLAZE_REALM = "production"
