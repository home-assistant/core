"""The Flume component."""
DOMAIN = "flume"

PLATFORMS = ["sensor"]

DEFAULT_NAME = "Flume Sensor"

FLUME_TYPE_SENSOR = 2
FLUME_QUERIES_SENSOR = {
    "current_interval": {"friendly_name": "Current", "unit_of_measurement": "gal/m"},
    "month_to_date": {"friendly_name": "Current Month", "unit_of_measurement": "gal"},
    "week_to_date": {"friendly_name": "Current Week", "unit_of_measurement": "gal"},
    "today": {"friendly_name": "Current Day", "unit_of_measurement": "gal"},
    "last_60_min": {"friendly_name": "60 Minutes", "unit_of_measurement": "gal/h"},
    "last_24_hrs": {"friendly_name": "24 Hours", "unit_of_measurement": "gal/d"},
    "last_30_days": {"friendly_name": "30 Days", "unit_of_measurement": "gal/mo"},
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
KEY_DEVICE_LOCATION_TIMEZONE = "tz"
