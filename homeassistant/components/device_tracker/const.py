"""Device tracker constants."""
from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from functools import partial
import logging
from typing import Final

from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

LOGGER: Final = logging.getLogger(__package__)

DOMAIN: Final = "device_tracker"
ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"

PLATFORM_TYPE_LEGACY: Final = "legacy"
PLATFORM_TYPE_ENTITY: Final = "entity_platform"


class SourceType(StrEnum):
    """Source type for device trackers."""

    GPS = "gps"
    ROUTER = "router"
    BLUETOOTH = "bluetooth"
    BLUETOOTH_LE = "bluetooth_le"


# SOURCE_TYPE_* below are deprecated as of 2022.9
# use the SourceType enum instead.
_DEPRECATED_SOURCE_TYPE_GPS: Final = DeprecatedConstantEnum(SourceType.GPS, "2025.1")
_DEPRECATED_SOURCE_TYPE_ROUTER: Final = DeprecatedConstantEnum(
    SourceType.ROUTER, "2025.1"
)
_DEPRECATED_SOURCE_TYPE_BLUETOOTH: Final = DeprecatedConstantEnum(
    SourceType.BLUETOOTH, "2025.1"
)
_DEPRECATED_SOURCE_TYPE_BLUETOOTH_LE: Final = DeprecatedConstantEnum(
    SourceType.BLUETOOTH_LE, "2025.1"
)

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

# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
