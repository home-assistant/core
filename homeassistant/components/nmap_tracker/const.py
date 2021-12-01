"""The Nmap Tracker integration."""
from typing import Final

DOMAIN: Final = "nmap_tracker"

PLATFORMS: Final = ["device_tracker"]

NMAP_TRACKED_DEVICES: Final = "nmap_tracked_devices"

# Interval in minutes to exclude devices from a scan while they are home
CONF_HOME_INTERVAL: Final = "home_interval"
CONF_OPTIONS: Final = "scan_options"
DEFAULT_OPTIONS: Final = "-F -T4 --min-rate 10 --host-timeout 5s"

TRACKER_SCAN_INTERVAL: Final = 120
