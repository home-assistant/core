"""Provides device automations for MQTT."""
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import ATTR_DISCOVERY_HASH, device_trigger
from .discovery import MQTT_DISCOVERY_NEW, clear_discovery_hash

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

    async def async_discover(discovery_payload):
        """Discover and add an MQTT device automation."""
        discovery_hash = discovery_payload.pop(ATTR_DISCOVERY_HASH)
        try:
            config = PLATFORM_SCHEMA(discovery_payload)
            if config[CONF_AUTOMATION_TYPE] == AUTOMATION_TYPE_TRIGGER:
                await device_trigger.async_setup_trigger(
                    hass, config, config_entry, discovery_hash
                )
        except Exception:
            if discovery_hash:
                clear_discovery_hash(hass, discovery_hash)
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format("device_automation", "mqtt"), async_discover
    )
