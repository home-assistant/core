"""Device tracker constants."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.backports.enum import StrEnum

LOGGER: Final = logging.getLogger(__package__)

DOMAIN: Final = "device_tracker"
ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"

PLATFORM_TYPE_LEGACY: Final = "legacy"
PLATFORM_TYPE_ENTITY: Final = "entity_platform"

# SOURCE_TYPE_* below are deprecated as of 2022.9
# use the SourceType enum instead.
SOURCE_TYPE_GPS: Final = "gps"
SOURCE_TYPE_ROUTER: Final = "router"
SOURCE_TYPE_BLUETOOTH: Final = "bluetooth"
SOURCE_TYPE_BLUETOOTH_LE: Final = "bluetooth_le"


class SourceType(StrEnum):
    """Source type for device trackers."""

    GPS = "gps"
    ROUTER = "router"
    BLUETOOTH = "bluetooth"
    BLUETOOTH_LE = "bluetooth_le"


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

CONNECTED_DEVICE_REGISTERED: Final = "device_tracker_connected_device_registered"
