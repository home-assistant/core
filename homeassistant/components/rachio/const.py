"""Constants for rachio."""

import http.client
import ssl

DEFAULT_NAME = "Rachio"

DOMAIN = "rachio"

CONF_CUSTOM_URL = "hass_url_override"
# Manual run length
CONF_MANUAL_RUN_MINS = "manual_run_mins"
DEFAULT_MANUAL_RUN_MINS = 10

# Keys used in the API JSON
KEY_DEVICE_ID = "deviceId"
KEY_IMAGE_URL = "imageUrl"
KEY_DEVICES = "devices"
KEY_ENABLED = "enabled"
KEY_EXTERNAL_ID = "externalId"
KEY_ID = "id"
KEY_NAME = "name"
KEY_MODEL = "model"
KEY_ON = "on"
KEY_STATUS = "status"
KEY_SUBTYPE = "subType"
KEY_SUMMARY = "summary"
KEY_SERIAL_NUMBER = "serialNumber"
KEY_MAC_ADDRESS = "macAddress"
KEY_TYPE = "type"
KEY_URL = "url"
KEY_USERNAME = "username"
KEY_ZONE_ID = "zoneId"
KEY_ZONE_NUMBER = "zoneNumber"
KEY_ZONES = "zones"

# Yes we really do get all these exceptions (hopefully rachiopy switches to requests)
RACHIO_API_EXCEPTIONS = (
    http.client.HTTPException,
    ssl.SSLError,
    OSError,
    AssertionError,
)
