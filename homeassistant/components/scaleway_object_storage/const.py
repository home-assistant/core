"""Constants for the Scaleway Object Storage integration."""

from collections.abc import Callable
from typing import Final

from homeassistant.const import CONF_REGION as HASS_CONF_REGION
from homeassistant.util.hass_dict import HassKey

DOMAIN = "scaleway_object_storage"

CONF_SECTION_CREDENTIALS: Final = "credentials"
CONF_ACCESS_KEY_ID: Final = "access_key_id"
CONF_SECRET_KEY: Final = "secret_key"
CONF_REGION: Final = HASS_CONF_REGION
CONF_BUCKET: Final = "bucket"
CONF_OBJECT_PREFIX: Final = "object_prefix"

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

HEADER_METADATA: Final[str] = "x-amz-meta-backup-info"
"""HTTP header used by the S3 API to store object metadata."""
