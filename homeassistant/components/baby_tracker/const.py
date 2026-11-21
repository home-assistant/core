"""Constants for Baby Tracker (Nighp)."""

from datetime import timedelta

DOMAIN = "baby_tracker"


CONF_DEVICE_UUID = "device_uuid"

# How often the account syncs. Fixed: Home Assistant's polling rules leave it to the user to
# poll faster with ``homeassistant.update_entity``.
SCAN_INTERVAL = timedelta(minutes=5)


# How Home Assistant names itself in the account's device list.
DEVICE_NAME = "Home Assistant"

STORAGE_VERSION = 1
