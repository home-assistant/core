"""Provides device automations for MQTT."""
import logging

import voluptuous as vol

from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from . import device_trigger
from .. import mqtt
from .const import ATTR_DISCOVERY_HASH
from .discovery import MQTT_DISCOVERY_DONE, MQTT_DISCOVERY_NEW, clear_discovery_hash

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

    async def async_discover(discovery_payload):
        """Discover and add an MQTT device automation."""
        discovery_data = discovery_payload.discovery_data
        try:
            config = PLATFORM_SCHEMA(discovery_payload)
            if config[CONF_AUTOMATION_TYPE] == AUTOMATION_TYPE_TRIGGER:
                await device_trigger.async_setup_trigger(
                    hass, config, config_entry, discovery_data
                )
        except Exception:
            discovery_hash = discovery_data[ATTR_DISCOVERY_HASH]
            clear_discovery_hash(hass, discovery_hash)
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
            )
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format("device_automation", "mqtt"), async_discover
    )
    hass.bus.async_listen(EVENT_DEVICE_REGISTRY_UPDATED, async_device_removed)
