"""Constants for the iBeacon Tracker integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "ibeacon"

PLATFORMS = [Platform.DEVICE_TRACKER, Platform.SENSOR]

SIGNAL_IBEACON_DEVICE_NEW = "ibeacon_tracker_new_device"
SIGNAL_IBEACON_DEVICE_UNAVAILABLE = "ibeacon_tracker_unavailable_device"
SIGNAL_IBEACON_DEVICE_SEEN = "ibeacon_seen_device"

ATTR_UUID = "uuid"
ATTR_MAJOR = "major"
ATTR_MINOR = "minor"
ATTR_SOURCE = "source"

UNAVAILABLE_TIMEOUT = 180  # Number of seconds we wait for a beacon to be seen before marking it unavailable

# How often to update RSSI if it has changed
# and look for unavailable groups that use a random MAC address
UPDATE_INTERVAL = timedelta(seconds=60)

# If a device broadcasts this many unique ids from the same address
# we will add it to the ignore list since its garbage data.
MAX_IDS = 10

# If a device broadcasts this many major minors for the same uuid
# we will add it to the ignore list since its garbage data.
MAX_IDS_PER_UUID = 50

CONF_IGNORE_ADDRESSES = "ignore_addresses"
CONF_IGNORE_UUIDS = "ignore_uuids"
