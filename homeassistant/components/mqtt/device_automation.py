"""Provides device automations for MQTT."""
import functools

import voluptuous as vol

from . import device_trigger
from .. import mqtt
from .mixins import async_setup_entry_helper

AUTOMATION_TYPE_TRIGGER = "trigger"
AUTOMATION_TYPES = [AUTOMATION_TYPE_TRIGGER]
AUTOMATION_TYPES_SCHEMA = vol.In(AUTOMATION_TYPES)
CONF_AUTOMATION_TYPE = "automation_type"

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_AUTOMATION_TYPE): AUTOMATION_TYPES_SCHEMA},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass, config_entry):
    """Set up MQTT device automation dynamically through MQTT discovery."""

    setup = functools.partial(_async_setup_automation, hass, config_entry=config_entry)
    await async_setup_entry_helper(hass, "device_automation", setup, PLATFORM_SCHEMA)


async def _async_setup_automation(hass, config, config_entry, discovery_data):
    """Set up an MQTT device automation."""
    if config[CONF_AUTOMATION_TYPE] == AUTOMATION_TYPE_TRIGGER:
        await device_trigger.async_setup_trigger(
            hass, config, config_entry, discovery_data
        )


async def async_removed_from_device(hass, device_id):
    """Handle Mqtt removed from a device."""
    await device_trigger.async_removed_from_device(hass, device_id)
