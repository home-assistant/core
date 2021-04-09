"""Constants for the sia integration."""
from datetime import timedelta

CONF_ACCOUNT = "account"
CONF_ACCOUNTS = "accounts"
CONF_ADDITIONAL_ACCOUNTS = "additional_account"
CONF_PING_INTERVAL = "ping_interval"
CONF_ENCRYPTION_KEY = "encryption_key"
CONF_ZONES = "zones"
CONF_IGNORE_TIMESTAMPS = "ignore_timestamps"

DOMAIN = "sia"
DATA_UPDATED = f"{DOMAIN}_data_updated"
SIA_EVENT = "sia_event"
HUB_SENSOR_NAME = "last_heartbeat"
HUB_ZONE = 0
PING_INTERVAL_MARGIN = timedelta(seconds=30)

EVENT_CODE = "last_code"
EVENT_ACCOUNT = "account"
EVENT_ZONE = "zone"
EVENT_PORT = "port"
EVENT_MESSAGE = "last_message"
EVENT_ID = "last_id"
EVENT_TIMESTAMP = "last_timestamp"
