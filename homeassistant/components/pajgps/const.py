"""Constants for the PajGPS integration."""

DOMAIN = "pajgps"
VERSION = "0.8.0"


# Update intervals (seconds)
DEVICES_INTERVAL = 300  # device list — rarely changes
POSITIONS_INTERVAL = 30  # positions + sensors — medium frequency

# Per-device request queue
REQUEST_DELAY = 0.2  # minimum gap between consecutive calls on the same device queue
