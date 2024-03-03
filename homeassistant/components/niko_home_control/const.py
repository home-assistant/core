"""Constants for niko_home_control integration."""
from datetime import timedelta

DEFAULT_PORT = 8000
DEFAULT_IP = "0.0.0.0"
DEFAULT_NAME = "Niko Home Control"
DOMAIN = "niko_home_control"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)
SCAN_INTERVAL = timedelta(seconds=30)
COVER_OPEN = 255
COVER_CLOSE = 254
COVER_STOP = 253
