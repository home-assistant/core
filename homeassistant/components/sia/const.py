"""Constants for the sia integration."""
from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)

PLATFORMS = [ALARM_CONTROL_PANEL_DOMAIN]

CONF_ACCOUNT = "account"
CONF_ACCOUNTS = "accounts"
CONF_ADDITIONAL_ACCOUNTS = "additional_account"
CONF_PING_INTERVAL = "ping_interval"
CONF_ENCRYPTION_KEY = "encryption_key"
CONF_ZONES = "zones"
CONF_IGNORE_TIMESTAMPS = "ignore_timestamps"

DOMAIN = "sia"
TITLE = "SIA Alarm on port {}"
SIA_EVENT = "sia_event_{}_{}"
SIA_NAME_FORMAT = "{} - {} - zone {} - {}"
SIA_NAME_FORMAT_HUB = "{} - {} - {}"
SIA_ENTITY_ID_FORMAT = "{}_{}_{}_{}"
SIA_ENTITY_ID_FORMAT_HUB = "{}_{}_{}"
SIA_UNIQUE_ID_FORMAT_ALARM = "{}_{}_{}"
SIA_UNIQUE_ID_FORMAT = "{}_{}_{}_{}"
HUB_SENSOR_NAME = "last_heartbeat"
HUB_ZONE = 0
PING_INTERVAL_MARGIN = 30

DEFAULT_TIMEBAND = (80, 40)
IGNORED_TIMEBAND = (3600, 1800)

ATTR_CODE = "last_code"
ATTR_ZONE = "zone"
ATTR_PORT = "port"
ATTR_MESSAGE = "last_message"
ATTR_ID = "last_id"
ATTR_TIMESTAMP = "last_timestamp"
