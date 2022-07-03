"""Support for tracking MQTT enabled devices."""
import voluptuous as vol

from homeassistant.components import device_tracker

from ..mixins import warn_for_legacy_schema
from .schema_discovery import PLATFORM_SCHEMA_MODERN  # noqa: F401
from .schema_discovery import async_setup_entry_from_discovery
from .schema_yaml import PLATFORM_SCHEMA_YAML, async_setup_scanner_from_yaml

# Configuring MQTT Device Trackers under the device_tracker platform key is deprecated in HA Core 2022.6
PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA_YAML, warn_for_legacy_schema(device_tracker.DOMAIN)
)
async_setup_scanner = async_setup_scanner_from_yaml
async_setup_entry = async_setup_entry_from_discovery
