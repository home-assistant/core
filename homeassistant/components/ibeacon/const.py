"""Constants for the iBeacon Tracker integration."""


DOMAIN = "ibeacon"

SIGNAL_IBEACON_DEVICE_NEW = "ibeacon_tracker_new_device"
SIGNAL_IBEACON_DEVICE_UNAVAILABLE = "ibeacon_tracker_unavailable_device"
SIGNAL_IBEACON_DEVICE_SEEN = "ibeacon_seen_device"

ATTR_UUID = "uuid"
ATTR_MAJOR = "major"
ATTR_MINOR = "minor"
ATTR_POWER = "power"
ATTR_RSSI = "rssi"
ATTR_SOURCE = "source"
ATTR_DISTANCE = "distance"

# If a device broadcasts this many unique ids from the same address
# we will add it to the ignore list since its garbage data.
MAX_IDS = 10

CONF_IGNORE_ADDRESSES = "ignore_addresses"
CONF_IGNORE_GROUP_IDS = "ignore_group_ids"

CONF_MIN_RSSI = "min_rssi"
DEFAULT_MIN_RSSI = -85
