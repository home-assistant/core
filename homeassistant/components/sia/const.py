"""Constants for the sia integration."""

from datetime import timedelta

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

CONF_ACCOUNT = "account"
CONF_ACCOUNTS = "accounts"
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

PLATFORMS = [SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN, ALARM_CONTROL_PANEL_DOMAIN]
