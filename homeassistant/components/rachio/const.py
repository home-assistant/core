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
KEY_DURATION = "totalDuration"
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
KEY_SCHEDULES = "scheduleRules"
KEY_FLEX_SCHEDULES = "flexScheduleRules"
KEY_SCHEDULE_ID = "scheduleId"
KEY_CUSTOM_SHADE = "customShade"
KEY_CUSTOM_CROP = "customCrop"

ATTR_ZONE_TYPE = "type"
ATTR_ZONE_SHADE = "shade"

# Yes we really do get all these exceptions (hopefully rachiopy switches to requests)
RACHIO_API_EXCEPTIONS = (
    http.client.HTTPException,
    ssl.SSLError,
    OSError,
    AssertionError,
)

STATUS_ONLINE = "ONLINE"
STATUS_OFFLINE = "OFFLINE"

SIGNAL_RACHIO_UPDATE = f"{DOMAIN}_update"
SIGNAL_RACHIO_CONTROLLER_UPDATE = f"{SIGNAL_RACHIO_UPDATE}_controller"
SIGNAL_RACHIO_ZONE_UPDATE = f"{SIGNAL_RACHIO_UPDATE}_zone"
SIGNAL_RACHIO_SCHEDULE_UPDATE = f"{SIGNAL_RACHIO_UPDATE}_schedule"

CONF_WEBHOOK_ID = "webhook_id"
CONF_CLOUDHOOK_URL = "cloudhook_url"
