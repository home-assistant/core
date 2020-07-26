"""The Flume component."""
DOMAIN = "flume"

PLATFORMS = ["sensor"]

DEFAULT_NAME = "Flume Sensor"

FLUME_TYPE_SENSOR = 2
FLUME_QUERIES_SENSOR = {
    "current_interval": "Current",
    "month_to_date": "Current Month",
    "week_to_date": "Current Week",
    "today": "Current Day",
    "last_60_min": "60 Minutes",
    "last_24_hrs": "24 Hours",
    "last_30_days": "30 Days",
}

FLUME_AUTH = "flume_auth"
FLUME_HTTP_SESSION = "http_session"
FLUME_DEVICES = "devices"


CONF_TOKEN_FILE = "token_filename"
BASE_TOKEN_FILENAME = "FLUME_TOKEN_FILE"


KEY_DEVICE_TYPE = "type"
KEY_DEVICE_ID = "id"
KEY_DEVICE_LOCATION = "location"
KEY_DEVICE_LOCATION_NAME = "name"
