"""Constants for the Cloudflare R2 integration."""

from collections.abc import Callable
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "cloudflare_r2"

CONF_ACCESS_KEY_ID = "access_key_id"
CONF_SECRET_ACCESS_KEY = "secret_access_key"
CONF_ENDPOINT_URL = "endpoint_url"
CONF_BUCKET = "bucket"
CONF_PREFIX = "prefix"

# R2 is S3-compatible. Endpoint should be like:
# https://<accountid>.r2.cloudflarestorage.com
CLOUDFLARE_R2_DOMAIN: Final = "r2.cloudflarestorage.com"
DEFAULT_ENDPOINT_URL: Final = "https://ACCOUNT_ID." + CLOUDFLARE_R2_DOMAIN + "/"

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)


DESCRIPTION_R2_AUTH_DOCS_URL: Final = "https://developers.cloudflare.com/r2/api/tokens/"
