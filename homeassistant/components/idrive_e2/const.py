"""Constants for the AWS S3 integration."""

from collections.abc import Callable
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "idrive_e2"

CONF_ACCESS_KEY_ID = "access_key_id"
CONF_SECRET_ACCESS_KEY = "secret_access_key"
CONF_ENDPOINT_URL = "endpoint_url"
CONF_BUCKET = "bucket"

GET_REGION_ENDPOINT_URL = "https://api.idrivee2.com/api/service/get_region_end_point"
GET_REGION_INVALID_CREDENTIALS_CODE = -3

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)
