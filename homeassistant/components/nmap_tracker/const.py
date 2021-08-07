"""The Nmap Tracker integration."""

DOMAIN = "nmap_tracker"

PLATFORMS = ["device_tracker"]

NMAP_TRACKED_DEVICES = "nmap_tracked_devices"

# Interval in minutes to exclude devices from a scan while they are home
CONF_HOME_INTERVAL = "home_interval"
CONF_OPTIONS = "scan_options"
DEFAULT_OPTIONS = "-F --host-timeout 5s"

TRACKER_SCAN_INTERVAL = 120

DEFAULT_TRACK_NEW_DEVICES = True
