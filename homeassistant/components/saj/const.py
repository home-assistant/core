"""Constants for the SAJ component."""
from datetime import timedelta

DEFAULT_NAME = "SAJ Solar inverter"
DOMAIN = "saj"
INVERTER_TYPES = ["ethernet", "wifi"]
UPDATE_INTERVAL = timedelta(seconds=30)
