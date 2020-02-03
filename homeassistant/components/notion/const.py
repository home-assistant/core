"""Define constants for the Notion integration."""
from datetime import timedelta

DOMAIN = "notion"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)

DATA_CLIENT = "client"

TOPIC_DATA_UPDATE = f"{DOMAIN}_data_update"

TYPE_BINARY_SENSOR = "binary_sensor"
TYPE_SENSOR = "sensor"
