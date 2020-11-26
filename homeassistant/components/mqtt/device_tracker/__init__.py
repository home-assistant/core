"""Support for tracking MQTT enabled devices."""
from .schema_discovery import async_setup_entry_from_discovery
from .schema_yaml import PLATFORM_SCHEMA_YAML, async_setup_scanner_from_yaml

PLATFORM_SCHEMA = PLATFORM_SCHEMA_YAML
async_setup_scanner = async_setup_scanner_from_yaml
async_setup_entry = async_setup_entry_from_discovery
