"""Constants for the sia integration."""

from datetime import timedelta

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)

CONF_ACCOUNT = "account"
CONF_ACCOUNTS = "accounts"
CONF_ADDITIONAL_ACCOUNTS = "additional_account"
CONF_PING_INTERVAL = "ping_interval"
CONF_ENCRYPTION_KEY = "encryption_key"
CONF_ZONES = "zones"
DOMAIN = "sia"
DATA_UPDATED = f"{DOMAIN}_data_updated"
DEFAULT_NAME = "SIA Alarm"
DEVICE_CLASS_ALARM = "alarm"
HUB_SENSOR_NAME = "last_heartbeat"
HUB_ZONE = 0
PING_INTERVAL_MARGIN = timedelta(seconds=30)
PREVIOUS_STATE = "previous_state"
UTCNOW = "utcnow"
LAST_MESSAGE = "last_message"

INVALID_KEY_FORMAT = "invalid_key_format"
INVALID_KEY_LENGTH = "invalid_key_length"
INVALID_ACCOUNT_FORMAT = "invalid_account_format"
INVALID_ACCOUNT_LENGTH = "invalid_account_length"
INVALID_PING = "invalid_ping"
INVALID_ZONES = "invalid_zones"

PLATFORMS = [ALARM_CONTROL_PANEL_DOMAIN]
