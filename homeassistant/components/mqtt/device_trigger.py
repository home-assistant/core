"""Provides device automations for MQTT."""
import logging
from typing import List

import attr
import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.automation import AutomationActionType
import homeassistant.components.automation.mqtt as automation_mqtt
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType

from . import (
    ATTR_DISCOVERY_HASH,
    CONF_CONNECTIONS,
    CONF_DEVICE,
    CONF_IDENTIFIERS,
    CONF_PAYLOAD,
    CONF_QOS,
    DOMAIN,
)
from .const import DEFAULT_QOS
from .discovery import MQTT_DISCOVERY_UPDATED, clear_discovery_hash

_LOGGER = logging.getLogger(__name__)

CONF_AUTOMATION_TYPE = "automation_type"
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
        vol.Optional(CONF_PAYLOAD, default=None): vol.Any(None, cv.string),
        vol.Optional(CONF_QOS, default=DEFAULT_QOS): vol.Coerce(int),
        vol.Required(CONF_TYPE): cv.string,
        vol.Required(CONF_SUBTYPE): cv.string,
    }
)

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_AUTOMATION_TYPE): str,
        vol.Required(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_PAYLOAD, default=None): vol.Any(None, cv.string),
        vol.Required(CONF_TYPE): cv.string,
        vol.Required(CONF_SUBTYPE): cv.string,
    },
    mqtt.validate_device_has_at_least_one_identifier,
)

DEVICE_TRIGGERS = "mqtt_device_triggers"


@attr.s(slots=True, frozen=True)
class Trigger:
    """Device trigger settings."""

    device_id = attr.ib(type=str)
    type = attr.ib(type=str)
    subtype = attr.ib(type=str)
    topic = attr.ib(type=str)
    payload = attr.ib(type=str)
    qos = attr.ib(type=int)
    discovery_hash = attr.ib(type=str)


def _update_trigger(hass, discovery_hash, config):
    for device_id, triggers in hass.data[DEVICE_TRIGGERS].items():
        if discovery_hash in triggers:
            triggers[discovery_hash] = Trigger(
                device_id=device_id,
                type=config[CONF_TYPE],
                subtype=config[CONF_SUBTYPE],
                topic=config[CONF_TOPIC],
                payload=config[CONF_PAYLOAD],
                qos=config[CONF_QOS],
                discovery_hash=discovery_hash,
            )


def _remove_trigger(hass, discovery_hash):
    for _, triggers in hass.data[DEVICE_TRIGGERS].items():
        triggers.pop(discovery_hash)


async def async_setup_trigger(
    hass, config, async_add_entities, config_entry, discovery_hash
):
    """Set up the MQTT device trigger."""
    config = PLATFORM_SCHEMA(config)
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
            _remove_trigger(hass, discovery_hash)
            clear_discovery_hash(hass, discovery_hash)
            remove_signal()
        else:
            # Non-empty payload: Update trigger
            _LOGGER.info("Updating trigger: %s", discovery_hash)
            payload.pop(ATTR_DISCOVERY_HASH)
            config = PLATFORM_SCHEMA(payload)
            _update_trigger(hass, discovery_hash, config)

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
        if DEVICE_TRIGGERS not in hass.data:
            hass.data[DEVICE_TRIGGERS] = {}
        if device.id not in hass.data[DEVICE_TRIGGERS]:
            hass.data[DEVICE_TRIGGERS][device.id] = {}
        hass.data[DEVICE_TRIGGERS][device.id][discovery_hash] = Trigger(
            device_id=device.id,
            type=config[CONF_TYPE],
            subtype=config[CONF_SUBTYPE],
            topic=config[CONF_TOPIC],
            payload=config[CONF_PAYLOAD],
            qos=config[CONF_QOS],
            discovery_hash=discovery_hash,
        )


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for MQTT devices."""
    triggers = []

    if DEVICE_TRIGGERS not in hass.data or device_id not in hass.data[DEVICE_TRIGGERS]:
        return triggers

    for _, auto in hass.data[DEVICE_TRIGGERS][device_id].items():
        trigger = dict(MQTT_TRIGGER)
        trigger.update(
            device_id=device_id,
            type=auto.type,
            subtype=auto.subtype,
            topic=auto.topic,
            payload=auto.payload,
            qos=auto.qos,
        )
        triggers.append(trigger)

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    config = TRIGGER_SCHEMA(config)

    mqtt_config = {
        automation_mqtt.CONF_TOPIC: config[CONF_TOPIC],
        automation_mqtt.CONF_ENCODING: DEFAULT_ENCODING,
        automation_mqtt.CONF_QOS: config[CONF_QOS],
    }
    if CONF_PAYLOAD in config:
        mqtt_config[CONF_PAYLOAD] = config[CONF_PAYLOAD]

    _LOGGER.info("Adding trigger: %s:%s", config[CONF_TOPIC], config[CONF_PAYLOAD])
    return await automation_mqtt.async_attach_trigger(
        hass, mqtt_config, action, automation_info
    )
