"""Support for Wireless Sensor Tags."""

DOMAIN = "wirelesstag"

# Default values for missing data
DEFAULT_TAG_NAME = "Unknown Tag"
DEFAULT_UUID = "unknown"

# Template for signal - first parameter is tag_id,
# second, tag manager mac address
SIGNAL_TAG_UPDATE = "wirelesstag.tag_info_updated_{}_{}"

# Template for signal - tag_id, sensor type and
# tag manager mac address
SIGNAL_BINARY_EVENT_UPDATE = "wirelesstag.binary_event_updated_{}_{}_{}"
