"""Support for tracking MQTT enabled devices."""
import voluptuous as vol

from homeassistant.components import device_tracker
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..mixins import warn_for_legacy_schema
from .schema_discovery import (  # noqa: F401
    PLATFORM_SCHEMA_MODERN,
    async_setup_entry_from_discovery,
)

# Configuring MQTT Device Trackers under the device_tracker platform key is deprecated in HA Core 2022.6
# Setup for the legacy YAML format was removed in HA Core 2022.12
PLATFORM_SCHEMA = vol.All(warn_for_legacy_schema(device_tracker.DOMAIN))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT device_tracker through configuration.yaml and dynamically through MQTT discovery."""
    await async_setup_entry_from_discovery(hass, config_entry, async_add_entities)
