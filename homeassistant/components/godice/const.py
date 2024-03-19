"""Constants for the godice integration."""
from datetime import timedelta

DOMAIN = "godice"
SCAN_INTERVAL = timedelta(seconds=60)

DATA_DEVICE = "device"
DATA_DEVICE_INFO = "device_info"
DATA_DISCONNECTED_BY_REQUEST_FLAG = "is_disconnected_by_request"
