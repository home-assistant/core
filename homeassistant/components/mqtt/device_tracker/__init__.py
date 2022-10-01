"""Support for tracking MQTT enabled devices."""
import voluptuous as vol

from homeassistant.components import device_tracker
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import MQTT_DATA_DEVICE_TRACKER_LEGACY
from ..mixins import warn_for_legacy_schema
from .schema_discovery import PLATFORM_SCHEMA_MODERN  # noqa: F401
from .schema_discovery import async_setup_entry_from_discovery
from .schema_yaml import (
    PLATFORM_SCHEMA_YAML,
    MQTTLegacyDeviceTrackerData,
    async_setup_scanner_from_yaml,
)

# Configuring MQTT Device Trackers under the device_tracker platform key is deprecated in HA Core 2022.6
PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA_YAML, warn_for_legacy_schema(device_tracker.DOMAIN)
)

# Legacy setup
async_setup_scanner = async_setup_scanner_from_yaml


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT device_tracker through configuration.yaml and dynamically through MQTT discovery."""
    await async_setup_entry_from_discovery(hass, config_entry, async_add_entities)
    # (re)load legacy service
    if MQTT_DATA_DEVICE_TRACKER_LEGACY in hass.data:
        yaml_device_tracker_data: MQTTLegacyDeviceTrackerData = hass.data[
            MQTT_DATA_DEVICE_TRACKER_LEGACY
        ]
        await async_setup_scanner_from_yaml(
            hass,
            config=yaml_device_tracker_data.config,
            async_see=yaml_device_tracker_data.async_see,
        )
