"""Constants for the Sequence integration."""

from datetime import timedelta

from homeassistant.const import CONF_ACCESS_TOKEN  # noqa: F401

DOMAIN = "getsequence"

# Update interval
SCAN_INTERVAL = timedelta(minutes=5)

# Device info
MANUFACTURER = "Sequence Fintech Inc."
MODEL = "Financial Orchestration Platform"
