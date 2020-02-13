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
from homeassistant.exceptions import HomeAssistantError
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
from .discovery import MQTT_DISCOVERY_UPDATED, clear_discovery_hash

_LOGGER = logging.getLogger(__name__)

CONF_AUTOMATION_TYPE = "automation_type"
CONF_DISCOVERY_ID = "discovery_id"
CONF_SUBTYPE = "subtype"
CONF_TOPIC = "topic"
DEFAULT_ENCODING = "utf-8"
DEVICE = "device"

MQTT_TRIGGER_BASE = {
    # Trigger when MQTT message is received
    CONF_PLATFORM: DEVICE,
    CONF_DOMAIN: DOMAIN,
}

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DEVICE,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_DISCOVERY_ID): str,
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
ATTACHED_DEVICE_TRIGGERS = "mqtt_attached_device_triggers"


@attr.s(slots=True, frozen=True)
class Trigger:
    """Device trigger settings."""

    device_id = attr.ib(type=str)
    type = attr.ib(type=str)
    subtype = attr.ib(type=str)
    topic = attr.ib(type=str)
    payload = attr.ib(type=str)
    qos = attr.ib(type=int)
    discovery_id = attr.ib(type=str)


@attr.s(slots=True)
class AttachedTrigger:
    """Device trigger settings."""

    device_id = attr.ib(type=str)
    discovery_id = attr.ib(type=str)
    action = attr.ib(type=AutomationActionType)
    automation_info = attr.ib(type=dict)
    remove = attr.ib(type=CALLBACK_TYPE)


async def _update_device(hass, config_entry, config):
    """Update device registry."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    config_entry_id = config_entry.entry_id
    device_info = mqtt.device_info_from_config(config[CONF_DEVICE])

    if config_entry_id is not None and device_info is not None:
        device_info["config_entry_id"] = config_entry_id
        device_registry.async_get_or_create(**device_info)


async def _attach_mqtt_trigger(hass, discovery_id, action, automation_info):
    """Attach MQTT trigger."""
    trigger = hass.data[DEVICE_TRIGGERS][discovery_id]
    mqtt_config = {
        automation_mqtt.CONF_TOPIC: trigger.topic,
        automation_mqtt.CONF_ENCODING: DEFAULT_ENCODING,
        automation_mqtt.CONF_QOS: trigger.qos,
    }
    if trigger.payload:
        mqtt_config[CONF_PAYLOAD] = trigger.payload

    return await automation_mqtt.async_attach_trigger(
        hass, mqtt_config, action, automation_info
    )


async def _update_trigger(hass, discovery_id, config):
    """Remove MQTT device trigger."""
    device_id = hass.data[DEVICE_TRIGGERS][discovery_id].device_id
    hass.data[DEVICE_TRIGGERS][discovery_id] = Trigger(
        device_id=device_id,
        type=config[CONF_TYPE],
        subtype=config[CONF_SUBTYPE],
        topic=config[CONF_TOPIC],
        payload=config[CONF_PAYLOAD],
        qos=config[CONF_QOS],
        discovery_id=discovery_id,
    )

    if ATTACHED_DEVICE_TRIGGERS not in hass.data:
        return

    # Unsubscribe+subscribe if this trigger is in use
    for trig in hass.data[ATTACHED_DEVICE_TRIGGERS]:
        if trig.discovery_id == discovery_id:
            if trig.remove:
                trig.remove()
            trig.remove = await _attach_mqtt_trigger(
                hass, discovery_id, trig.action, trig.automation_info
            )


def _remove_trigger(hass, discovery_id):
    """Remove MQTT device trigger."""
    trigger = hass.data[DEVICE_TRIGGERS].pop(discovery_id)

    if not trigger:
        return

    discovery_id = trigger.discovery_id
    # Unsubscribe if this trigger is in use
    for trig in hass.data[ATTACHED_DEVICE_TRIGGERS]:
        if trig.discovery_id == discovery_id:
            if trig.remove:
                trig.remove()


async def async_setup_trigger(hass, config, config_entry, discovery_hash):
    """Set up the MQTT device trigger."""
    config = PLATFORM_SCHEMA(config)
    discovery_id = discovery_hash[1]
    remove_signal = None

    async def discovery_update(payload):
        """Handle discovery update."""
        _LOGGER.info(
            "Got update for trigger with hash: %s '%s'", discovery_hash, payload
        )
        if not payload:
            # Empty payload: Remove trigger
            _LOGGER.info("Removing trigger: %s", discovery_hash)
            _remove_trigger(hass, discovery_id)
            clear_discovery_hash(hass, discovery_hash)
            remove_signal()
        else:
            # Non-empty payload: Update trigger
            _LOGGER.info("Updating trigger: %s", discovery_hash)
            payload.pop(ATTR_DISCOVERY_HASH)
            config = PLATFORM_SCHEMA(payload)
            await _update_device(hass, config_entry, config)
            await _update_trigger(hass, discovery_id, config)

    remove_signal = async_dispatcher_connect(
        hass, MQTT_DISCOVERY_UPDATED.format(discovery_hash), discovery_update
    )

    await _update_device(hass, config_entry, config)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_device(
        {(DOMAIN, id_) for id_ in config[CONF_DEVICE][CONF_IDENTIFIERS]},
        {tuple(x) for x in config[CONF_DEVICE][CONF_CONNECTIONS]},
    )

    if device is None:
        return

    if DEVICE_TRIGGERS not in hass.data:
        hass.data[DEVICE_TRIGGERS] = {}
    hass.data[DEVICE_TRIGGERS][discovery_id] = Trigger(
        device_id=device.id,
        type=config[CONF_TYPE],
        subtype=config[CONF_SUBTYPE],
        topic=config[CONF_TOPIC],
        payload=config[CONF_PAYLOAD],
        qos=config[CONF_QOS],
        discovery_id=discovery_id,
    )

    if ATTACHED_DEVICE_TRIGGERS not in hass.data:
        return

    # If someone was waiting for this trigger to be discovered, subscribe now
    for trig in hass.data[ATTACHED_DEVICE_TRIGGERS]:
        if trig.discovery_id == discovery_id:
            trig.remove = await _attach_mqtt_trigger(
                hass, discovery_id, trig.action, trig.automation_info
            )


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for MQTT devices."""
    triggers = []

    if DEVICE_TRIGGERS not in hass.data:
        return triggers

    for trig in hass.data[DEVICE_TRIGGERS].values():
        if trig.device_id != device_id:
            continue

        trigger = {
            **MQTT_TRIGGER_BASE,
            "device_id": device_id,
            "type": trig.type,
            "subtype": trig.subtype,
            "discovery_id": trig.discovery_id,
        }
        triggers.append(trigger)

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    if ATTACHED_DEVICE_TRIGGERS not in hass.data:
        hass.data[ATTACHED_DEVICE_TRIGGERS] = []
    config = TRIGGER_SCHEMA(config)
    device_id = config[CONF_DEVICE_ID]
    discovery_id = config[CONF_DISCOVERY_ID]
    mqtt_remove = None

    if DEVICE_TRIGGERS in hass.data and discovery_id in hass.data[DEVICE_TRIGGERS]:
        # If we know about the trigger, subscribe to MQTT topic
        mqtt_remove = await _attach_mqtt_trigger(
            hass, discovery_id, action, automation_info
        )

    attached_trigger = AttachedTrigger(
        device_id, discovery_id, action, automation_info, mqtt_remove
    )
    hass.data[ATTACHED_DEVICE_TRIGGERS].append(attached_trigger)

    @callback
    def async_remove() -> None:
        """Remove trigger."""
        if attached_trigger not in hass.data[ATTACHED_DEVICE_TRIGGERS]:
            raise HomeAssistantError("Can't remove trigger twice")

        index = hass.data[ATTACHED_DEVICE_TRIGGERS].index(attached_trigger)
        hass.data[ATTACHED_DEVICE_TRIGGERS][index].remove()
        hass.data[ATTACHED_DEVICE_TRIGGERS].pop(index)

    return async_remove
