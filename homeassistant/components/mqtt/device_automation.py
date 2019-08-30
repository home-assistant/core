"""Provides device automations for mqtt."""
import logging

import attr
import voluptuous as vol

from homeassistant.components import mqtt
import homeassistant.components.automation.mqtt as automation_mqtt
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from . import (
    ATTR_DISCOVERY_HASH,
    CONF_CONNECTIONS,
    CONF_DEVICE,
    CONF_IDENTIFIERS,
    CONF_PAYLOAD,
    CONF_QOS,
    DOMAIN,
)
from .discovery import MQTT_DISCOVERY_NEW, MQTT_DISCOVERY_UPDATED, clear_discovery_hash

_LOGGER = logging.getLogger(__name__)

# mypy: allow-untyped-defs, no-check-untyped-defs

CONF_ENCODING = "encoding"
DEFAULT_ENCODING = "utf-8"
CONF_TOPIC = "topic"

CONF_AUTOMATION_TYPE = "automation_type"
AUTOMATION_TYPE_TRIGGER = "trigger"
AUTOMATION_TYPES = [AUTOMATION_TYPE_TRIGGER]
AUTOMATION_TYPES_SCHEMA = vol.In(AUTOMATION_TYPES)

MQTT_TRIGGER = {
    # Trigger when MQTT message is received
    CONF_PLATFORM: "device",
    CONF_DOMAIN: DOMAIN,
}

TRIGGER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_PLATFORM): "device",
            vol.Required(CONF_DOMAIN): DOMAIN,
            vol.Optional(CONF_DEVICE_ID): str,
            vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_PAYLOAD): cv.string,
            vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
            vol.Optional(CONF_TYPE): cv.string,
            vol.Optional(CONF_EVENT): cv.string,
        }
    )
)

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_AUTOMATION_TYPE): AUTOMATION_TYPES_SCHEMA,
        vol.Required(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_PAYLOAD, default=None): vol.Any(None, cv.string),
        vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
        vol.Optional(CONF_TYPE): cv.string,
        vol.Optional(CONF_EVENT): cv.string,
    },
    mqtt.validate_device_has_at_least_one_identifier,  # Why here?
)

DEVICE_AUTOMATIONS = "mqtt_device_automations"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT device automation dynamically through MQTT discovery."""

    async def async_discover(discovery_payload):
        """Discover and add an MQTT device automation."""
        try:
            discovery_hash = discovery_payload.pop(ATTR_DISCOVERY_HASH)
            config = PLATFORM_SCHEMA(discovery_payload)
            await _async_setup_automation(
                hass, config, async_add_entities, config_entry, discovery_hash
            )
        except Exception:
            if discovery_hash:
                clear_discovery_hash(hass, discovery_hash)
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format("device_automation", "mqtt"), async_discover
    )


@attr.s(slots=True, frozen=True)
class Automation:
    """Device automation settings."""

    device_id = attr.ib(type=str)
    automation_type = attr.ib(type=str)
    type = attr.ib(type=str)
    event = attr.ib(type=str)
    topic = attr.ib(type=str)
    payload = attr.ib(type=str)
    encoding = attr.ib(type=str)
    qos = attr.ib(type=int)
    discovery_hash = attr.ib(type=str)


def _update_automation(hass, discovery_hash, config):
    for device_id, automations in hass.data[DEVICE_AUTOMATIONS].items():
        if discovery_hash in automations:
            automations[discovery_hash] = Automation(
                device_id=device_id,
                automation_type=config[CONF_AUTOMATION_TYPE],
                type=config[CONF_TYPE],
                event=config[CONF_EVENT],
                topic=config[CONF_TOPIC],
                payload=config[CONF_PAYLOAD],
                encoding=config[CONF_ENCODING],
                qos=config[CONF_QOS],
                discovery_hash=discovery_hash,
            )


def _remove_automation(hass, discovery_hash):
    for _, automations in hass.data[DEVICE_AUTOMATIONS].items():
        automations.pop(discovery_hash)


async def _async_setup_automation(
    hass, config, async_add_entities, config_entry, discovery_hash
):
    """Set up the MQTT device automation."""
    remove_signal = None

    @callback
    def discovery_callback(payload):
        """Handle discovery update."""
        _LOGGER.info(
            "Got update for trigger with hash: %s '%s'", discovery_hash, payload
        )
        if not payload:
            # Empty payload: Remove trigger
            _LOGGER.info("Removing trigger: %s", discovery_hash)
            _remove_automation(hass, discovery_hash)
            clear_discovery_hash(hass, discovery_hash)
            remove_signal()
        else:
            # Non-empty payload: Update automation
            _LOGGER.info("Updating trigger: %s", discovery_hash)
            payload.pop(ATTR_DISCOVERY_HASH)
            config = PLATFORM_SCHEMA(payload)
            _update_automation(hass, discovery_hash, config)

    remove_signal = async_dispatcher_connect(
        hass, MQTT_DISCOVERY_UPDATED.format(discovery_hash), discovery_callback
    )

    device_registry = await hass.helpers.device_registry.async_get_registry()
    config_entry_id = config_entry.entry_id
    device_info = mqtt.device_info_from_config(config[CONF_DEVICE])

    if config_entry_id is not None and device_info is not None:
        device_info["config_entry_id"] = config_entry_id
        device_registry.async_get_or_create(**device_info)

    device = device_registry.async_get_device(
        {(DOMAIN, id_) for id_ in config[CONF_DEVICE][CONF_IDENTIFIERS]},
        {tuple(x) for x in config[CONF_DEVICE][CONF_CONNECTIONS]},
    )

    if device is not None:
        if DEVICE_AUTOMATIONS not in hass.data:
            hass.data[DEVICE_AUTOMATIONS] = {}
        if device.id not in hass.data[DEVICE_AUTOMATIONS]:
            hass.data[DEVICE_AUTOMATIONS][device.id] = {}
        hass.data[DEVICE_AUTOMATIONS][device.id][discovery_hash] = Automation(
            device_id=device.id,
            automation_type=config[CONF_AUTOMATION_TYPE],
            type=config[CONF_TYPE],
            event=config[CONF_EVENT],
            topic=config[CONF_TOPIC],
            payload=config[CONF_PAYLOAD],
            encoding=config[CONF_ENCODING],
            qos=config[CONF_QOS],
            discovery_hash=discovery_hash,
        )


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for MQTT messages based on configuration."""
    mqtt_config = {
        automation_mqtt.CONF_TOPIC: config[CONF_TOPIC],
        automation_mqtt.CONF_ENCODING: config[CONF_ENCODING],
    }
    if CONF_PAYLOAD in config:
        mqtt_config[CONF_PAYLOAD] = config[CONF_PAYLOAD]

    return await automation_mqtt.async_trigger(
        hass, mqtt_config, action, automation_info
    )


async def async_trigger(hass, config, action, automation_info):
    """Temporary so existing automation framework can be used for testing."""
    return await async_attach_trigger(hass, config, action, automation_info)


async def async_get_triggers(hass, device_id):
    """List device triggers."""
    triggers = []

    if (
        DEVICE_AUTOMATIONS not in hass.data
        or device_id not in hass.data[DEVICE_AUTOMATIONS]
    ):
        return triggers

    for _, auto in hass.data[DEVICE_AUTOMATIONS][device_id].items():
        if auto.automation_type == AUTOMATION_TYPE_TRIGGER:
            trigger = dict(MQTT_TRIGGER)
            trigger.update(
                device_id=device_id,
                topic=auto.topic,
                payload=auto.payload,
                encoding=auto.encoding,
                type=auto.type,
                event=auto.event,
            )
            triggers.append(trigger)

    return triggers
