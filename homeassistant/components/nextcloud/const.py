"""Constants for Nextcloud integration."""
from datetime import timedelta

DOMAIN = "nextcloud"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_VERIFY_SSL = True


def isbool(val):
    """Test if value is a Nextcloud boolean value."""
    return isinstance(val, bool) or val in ["yes", "no"]


def istrue(val):
    """Test if value is a Nextcloud true value."""
    return val is True or val in ["yes"]
