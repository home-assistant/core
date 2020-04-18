"""Device tracker constants."""
from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "device_tracker"

PLATFORM_TYPE_LEGACY = "legacy"
PLATFORM_TYPE_ENTITY = "entity_platform"

SOURCE_TYPE_GPS = "gps"
SOURCE_TYPE_ROUTER = "router"
SOURCE_TYPE_BLUETOOTH = "bluetooth"
SOURCE_TYPE_BLUETOOTH_LE = "bluetooth_le"

CONF_SCAN_INTERVAL = "interval_seconds"
SCAN_INTERVAL = timedelta(seconds=12)

CONF_TRACK_NEW = "track_new_devices"
DEFAULT_TRACK_NEW = True

CONF_CONSIDER_HOME = "consider_home"
DEFAULT_CONSIDER_HOME = timedelta(seconds=180)

CONF_NEW_DEVICE_DEFAULTS = "new_device_defaults"

ATTR_ATTRIBUTES = "attributes"
ATTR_BATTERY = "battery"
ATTR_DEV_ID = "dev_id"
ATTR_GPS = "gps"
ATTR_HOST_NAME = "host_name"
ATTR_LOCATION_NAME = "location_name"
ATTR_MAC = "mac"
ATTR_SOURCE_TYPE = "source_type"
ATTR_CONSIDER_HOME = "consider_home"
