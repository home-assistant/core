"""Constants for the sia integration."""
from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN

PLATFORMS = [ALARM_CONTROL_PANEL_DOMAIN, BINARY_SENSOR_DOMAIN]

DOMAIN = "sia"

ATTR_CODE = "last_code"
ATTR_ZONE = "last_zone"
ATTR_MESSAGE = "last_message"
ATTR_ID = "last_id"
ATTR_TIMESTAMP = "last_timestamp"

TITLE = "SIA Alarm on port {}"
CONF_ACCOUNT = "account"
CONF_ACCOUNTS = "accounts"
CONF_ADDITIONAL_ACCOUNTS = "additional_account"
CONF_ENCRYPTION_KEY = "encryption_key"
CONF_IGNORE_TIMESTAMPS = "ignore_timestamps"
CONF_PING_INTERVAL = "ping_interval"
CONF_ZONES = "zones"

SIA_NAME_FORMAT = "{} - {} - zone {} - {}"
SIA_UNIQUE_ID_FORMAT_ALARM = "{}_{}_{}"
SIA_UNIQUE_ID_FORMAT_BINARY = "{}_{}_{}_{}"
SIA_HUB_ZONE = 0

SIA_EVENT = "sia_event_{}_{}"
