"""Constants for OPNsense component."""

from datetime import timedelta

DOMAIN = "opnsense"

CONF_API_SECRET = "api_secret"
CONF_TRACKER_INTERFACES = "tracker_interfaces"

# Update interval for device scanning
SCAN_INTERVAL = timedelta(seconds=30)
