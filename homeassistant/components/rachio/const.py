"""Constants for rachio."""

DEFAULT_NAME = "Rachio"

DOMAIN = "rachio"

CONF_CUSTOM_URL = "hass_url_override"
# Manual run length
CONF_MANUAL_RUN_MINS = "manual_run_mins"
DEFAULT_MANUAL_RUN_MINS = 10

# Slope constants
SLOPE_FLAT = "ZERO_THREE"
SLOPE_SLIGHT = "FOUR_SIX"
SLOPE_MODERATE = "SEVEN_TWELVE"
SLOPE_STEEP = "OVER_TWELVE"

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
KEY_RAIN_DELAY = "rainDelayExpirationDate"
KEY_RAIN_DELAY_END = "endTime"
KEY_RAIN_SENSOR_TRIPPED = "rainSensorTripped"
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
KEY_CUSTOM_SLOPE = "customSlope"

STATUS_ONLINE = "ONLINE"

MODEL_GENERATION_1 = "GENERATION1"
SCHEDULE_TYPE_FIXED = "FIXED"
SCHEDULE_TYPE_FLEX = "FLEX"
SERVICE_PAUSE_WATERING = "pause_watering"
SERVICE_RESUME_WATERING = "resume_watering"
SERVICE_STOP_WATERING = "stop_watering"
SERVICE_SET_ZONE_MOISTURE = "set_zone_moisture_percent"
SERVICE_START_MULTIPLE_ZONES = "start_multiple_zone_schedule"

SIGNAL_RACHIO_UPDATE = f"{DOMAIN}_update"
SIGNAL_RACHIO_CONTROLLER_UPDATE = f"{SIGNAL_RACHIO_UPDATE}_controller"
SIGNAL_RACHIO_RAIN_DELAY_UPDATE = f"{SIGNAL_RACHIO_UPDATE}_rain_delay"
SIGNAL_RACHIO_RAIN_SENSOR_UPDATE = f"{SIGNAL_RACHIO_UPDATE}_rain_sensor"
SIGNAL_RACHIO_ZONE_UPDATE = f"{SIGNAL_RACHIO_UPDATE}_zone"
SIGNAL_RACHIO_SCHEDULE_UPDATE = f"{SIGNAL_RACHIO_UPDATE}_schedule"

CONF_WEBHOOK_ID = "webhook_id"
CONF_CLOUDHOOK_URL = "cloudhook_url"
