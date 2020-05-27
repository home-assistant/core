"""Constants for the sia integration."""

from datetime import timedelta

DOMAIN = "sia"
DEFAULT_NAME = "SIA Alarm"
DATA_UPDATED = f"{DOMAIN}_data_updated"
PING_INTERVAL_MARGIN = timedelta(seconds=30)
CONF_ACCOUNT = "account"
CONF_ACCOUNTS = "accounts"
CONF_PING_INTERVAL = "ping_interval"
CONF_ENCRYPTION_KEY = "encryption_key"
CONF_ZONES = "zones"
PREVIOUS_STATE = "PREVIOUS_STATE"
