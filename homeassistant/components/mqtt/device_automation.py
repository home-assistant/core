"""Provides device automations for MQTT."""
import functools
import logging

import voluptuous as vol

from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED

from . import device_trigger
from .. import mqtt
from .mixins import async_setup_entry_helper

_LOGGER = logging.getLogger(__name__)

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

    async def async_device_removed(event):
        """Handle the removal of a device."""
        if event.data["action"] != "remove":
            return
        await device_trigger.async_device_removed(hass, event.data["device_id"])

    setup = functools.partial(_async_setup_automation, hass, config_entry=config_entry)
    await async_setup_entry_helper(hass, "device_automation", setup, PLATFORM_SCHEMA)
    hass.bus.async_listen(EVENT_DEVICE_REGISTRY_UPDATED, async_device_removed)


async def _async_setup_automation(hass, config, config_entry, discovery_data):
    """Set up an MQTT device automation."""
    if config[CONF_AUTOMATION_TYPE] == AUTOMATION_TYPE_TRIGGER:
        await device_trigger.async_setup_trigger(
            hass, config, config_entry, discovery_data
        )
