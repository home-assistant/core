"""Constants for the AirTouch 3 Air Conditioner integration."""

from datetime import timedelta

DOMAIN = "airtouch3"

DEFAULT_NAME = "AirTouch 3 Air Conditioner"
DISCOVERY_ATTEMPTS = 2
DISCOVERY_INTERVAL = timedelta(minutes=15)
DISCOVERY_MESSAGE = b"HF-A11ASSISTHREAD"
DISCOVERY_PORT = 49003
DISCOVERY_SEND_INTERVAL = 0.5
DISCOVERY_TIMEOUT = 5
