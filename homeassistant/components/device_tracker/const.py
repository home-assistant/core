"""Device tracker constants."""
from datetime import timedelta
import logging
from typing import Final

LOGGER: Final = logging.getLogger(__package__)

DOMAIN: Final = "device_tracker"

PLATFORM_TYPE_LEGACY: Final = "legacy"
PLATFORM_TYPE_ENTITY: Final = "entity_platform"

SOURCE_TYPE_GPS: Final = "gps"
SOURCE_TYPE_ROUTER: Final = "router"
SOURCE_TYPE_BLUETOOTH: Final = "bluetooth"
SOURCE_TYPE_BLUETOOTH_LE: Final = "bluetooth_le"

CONF_SCAN_INTERVAL: Final = "interval_seconds"
SCAN_INTERVAL: Final = timedelta(seconds=12)

CONF_TRACK_NEW: Final = "track_new_devices"
DEFAULT_TRACK_NEW: Final = True

CONF_CONSIDER_HOME: Final = "consider_home"
DEFAULT_CONSIDER_HOME: Final = timedelta(seconds=180)

CONF_NEW_DEVICE_DEFAULTS: Final = "new_device_defaults"

ATTR_ATTRIBUTES: Final = "attributes"
ATTR_BATTERY: Final = "battery"
ATTR_DEV_ID: Final = "dev_id"
ATTR_GPS: Final = "gps"
ATTR_HOST_NAME: Final = "host_name"
ATTR_LOCATION_NAME: Final = "location_name"
ATTR_MAC: Final = "mac"
ATTR_SOURCE_TYPE: Final = "source_type"
ATTR_CONSIDER_HOME: Final = "consider_home"
ATTR_IP: Final = "ip"
