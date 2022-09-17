"""Constants for the iBeacon Tracker integration."""

DOMAIN = "ibeacon"

SIGNAL_IBEACON_DEVICE_NEW = "ibeacon_tracker_new_device"
SIGNAL_IBEACON_DEVICE_UNAVAILABLE = "ibeacon_tracker_unavailable_device"
SIGNAL_IBEACON_DEVICE_SEEN = "ibeacon_seen_device"

ATTR_UUID = "uuid"
ATTR_MAJOR = "major"
ATTR_MINOR = "minor"
ATTR_POWER_BY_ADDRESS = "power_by_address"
ATTR_RSSI_BY_ADDRESS = "rssi_by_address"
ATTR_SOURCE_BY_ADDRESS = "source_by_address"
ATTR_DISTANCE_BY_ADDRESS = "distance_by_address"

# If a device broadcasts this many unique ids from the same address
# we will add it to the ignore list since its garbage data.
MAX_UNIQUE_IDS_PER_ADDRESS = 5

CONF_IGNORE_ADDRESSES = "ignore_addresses"
CONF_MIN_RSSI = "min_rssi"
DEFAULT_MIN_RSSI = -85

APPLE_MFR_ID = 76
IBEACON_FIRST_BYTE = 0x02
IBEACON_SECOND_BYTE = 0x15
