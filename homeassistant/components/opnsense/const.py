"""Constants for OPNsense component."""

from datetime import timedelta

DOMAIN = "opnsense"

CONF_API_SECRET = "api_secret"
CONF_TRACKER_INTERFACES = "tracker_interfaces"

# Update interval for device scanning
SCAN_INTERVAL = timedelta(seconds=30)


def get_firmware_privilege_issue_id(entry_id: str) -> str:
    """Return the missing firmware privilege issue ID for a config entry."""
    return f"firmware_privilege_missing_{entry_id}"
