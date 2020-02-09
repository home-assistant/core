"""Provides device automations for MQTT."""
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import ATTR_DISCOVERY_HASH, CONF_PAYLOAD, DOMAIN, device_trigger
from .discovery import MQTT_DISCOVERY_NEW, clear_discovery_hash

_LOGGER = logging.getLogger(__name__)

AUTOMATION_TYPE_TRIGGER = "trigger"
AUTOMATION_TYPES = [AUTOMATION_TYPE_TRIGGER]
AUTOMATION_TYPES_SCHEMA = vol.In(AUTOMATION_TYPES)
CONF_AUTOMATION_TYPE = "automation_type"
CONF_ENCODING = "encoding"
CONF_SUBTYPE = "subtype"
CONF_TOPIC = "topic"
DEFAULT_ENCODING = "utf-8"
DEVICE = "device"

MQTT_TRIGGER = {
    # Trigger when MQTT message is received
    CONF_PLATFORM: DEVICE,
    CONF_DOMAIN: DOMAIN,
}

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DEVICE,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Optional(CONF_DEVICE_ID): str,
        vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_PAYLOAD): cv.string,
        vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
        vol.Required(CONF_TYPE): cv.string,
        vol.Required(CONF_SUBTYPE): cv.string,
    }
)

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_AUTOMATION_TYPE): AUTOMATION_TYPES_SCHEMA},
    extra=vol.ALLOW_EXTRA,
)

DEVICE_TRIGGERS = "mqtt_device_triggers"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT device automation dynamically through MQTT discovery."""

    async def async_discover(discovery_payload):
        """Discover and add an MQTT device automation."""
        try:
            discovery_hash = discovery_payload.pop(ATTR_DISCOVERY_HASH)
            config = PLATFORM_SCHEMA(discovery_payload)
            if config[CONF_AUTOMATION_TYPE] == AUTOMATION_TYPE_TRIGGER:
                await device_trigger.async_setup_trigger(
                    hass, config, async_add_entities, config_entry, discovery_hash
                )
        except Exception:
            if discovery_hash:
                clear_discovery_hash(hass, discovery_hash)
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format("device_automation", "mqtt"), async_discover
    )
