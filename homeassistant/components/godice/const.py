"""Constants for the godice integration."""
from datetime import timedelta

DOMAIN = "godice"
SCAN_INTERVAL = timedelta(seconds=60)

MANUFACTURER = "Particula"
MODEL = "GoDice"

CONF_SHELL = "shell"
DATA_DICE = "dice"
DATA_DISCONNECTED_BY_REQUEST_FLAG = "is_disconnected_by_request"
