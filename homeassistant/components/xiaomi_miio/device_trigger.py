"""Provides device automations for Xiaomi Miio."""
import logging
import voluptuous as vol
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)

from .const import (
    DOMAIN,
    KEY_DEVICE,
}

_LOGGER = logging.getLogger(__name__)

TRIGGER_TYPES = {"water_detected", "noise_detected"}

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): str,
    }
)

async def async_get_triggers(hass, device_id):
    """Return a list of triggers."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(device_id)

    for config_entry in device.config_entries:
        _LOGGER.error(config_entry)

    #gateway = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]


    triggers = []

    #triggers.append({
    #    # Required fields of TRIGGER_BASE_SCHEMA
    #    CONF_PLATFORM: "device",
    #    CONF_DOMAIN: "mydomain",
    #    CONF_DEVICE_ID: device_id,
    #    # Required fields of TRIGGER_SCHEMA
    #    CONF_TYPE: "water_detected",
    #})

    return triggers