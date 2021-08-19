"""Provides device automations for MQTT."""
from __future__ import annotations

import logging
from typing import Callable

import attr
import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.typing import ConfigType

from . import CONF_PAYLOAD, CONF_QOS, DOMAIN, debug_info, trigger as mqtt_trigger
from .. import mqtt
from .const import ATTR_DISCOVERY_HASH, ATTR_DISCOVERY_TOPIC
from .discovery import MQTT_DISCOVERY_DONE, MQTT_DISCOVERY_UPDATED, clear_discovery_hash
from .mixins import (
    CONF_CONNECTIONS,
    CONF_IDENTIFIERS,
    MQTT_ENTITY_DEVICE_INFO_SCHEMA,
    cleanup_device_registry,
    device_info_from_config,
    validate_device_has_at_least_one_identifier,
)

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

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DEVICE,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_DISCOVERY_ID): str,
        vol.Required(CONF_TYPE): cv.string,
        vol.Required(CONF_SUBTYPE): cv.string,
    }
)

TRIGGER_DISCOVERY_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_AUTOMATION_TYPE): str,
        vol.Required(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        vol.Optional(CONF_PAYLOAD, default=None): vol.Any(None, cv.string),
        vol.Required(CONF_SUBTYPE): cv.string,
        vol.Required(CONF_TOPIC): cv.string,
        vol.Required(CONF_TYPE): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE, default=None): vol.Any(None, cv.string),
    },
    validate_device_has_at_least_one_identifier,
)

DEVICE_TRIGGERS = "mqtt_device_triggers"


@attr.s(slots=True)
class TriggerInstance:
    """Attached trigger settings."""

    action: AutomationActionType = attr.ib()
    automation_info: dict = attr.ib()
    trigger: Trigger = attr.ib()
    remove: CALLBACK_TYPE | None = attr.ib(default=None)

    async def async_attach_trigger(self):
        """Attach MQTT trigger."""
        mqtt_config = {
            mqtt_trigger.CONF_PLATFORM: mqtt.DOMAIN,
            mqtt_trigger.CONF_TOPIC: self.trigger.topic,
            mqtt_trigger.CONF_ENCODING: DEFAULT_ENCODING,
            mqtt_trigger.CONF_QOS: self.trigger.qos,
        }
        if self.trigger.payload:
            mqtt_config[CONF_PAYLOAD] = self.trigger.payload
        if self.trigger.value_template:
            mqtt_config[CONF_VALUE_TEMPLATE] = self.trigger.value_template
        mqtt_config = mqtt_trigger.TRIGGER_SCHEMA(mqtt_config)

        if self.remove:
            self.remove()
        self.remove = await mqtt_trigger.async_attach_trigger(
            self.trigger.hass,
            mqtt_config,
            self.action,
            self.automation_info,
        )


@attr.s(slots=True)
class Trigger:
    """Device trigger settings."""

    device_id: str = attr.ib()
    discovery_data: dict | None = attr.ib()
    hass: HomeAssistant = attr.ib()
    payload: str | None = attr.ib()
    qos: int | None = attr.ib()
    remove_signal: Callable[[], None] | None = attr.ib()
    subtype: str = attr.ib()
    topic: str | None = attr.ib()
    type: str = attr.ib()
    value_template: str | None = attr.ib()
    trigger_instances: list[TriggerInstance] = attr.ib(factory=list)

    async def add_trigger(self, action, automation_info):
        """Add MQTT trigger."""
        instance = TriggerInstance(action, automation_info, self)
        self.trigger_instances.append(instance)

        if self.topic is not None:
            # If we know about the trigger, subscribe to MQTT topic
            await instance.async_attach_trigger()

        @callback
        def async_remove() -> None:
            """Remove trigger."""
            if instance not in self.trigger_instances:
                raise HomeAssistantError("Can't remove trigger twice")

            if instance.remove:
                instance.remove()
            self.trigger_instances.remove(instance)

        return async_remove

    async def update_trigger(self, config, discovery_hash, remove_signal):
        """Update MQTT device trigger."""
        self.remove_signal = remove_signal
        self.type = config[CONF_TYPE]
        self.subtype = config[CONF_SUBTYPE]
        self.payload = config[CONF_PAYLOAD]
        self.qos = config[CONF_QOS]
        topic_changed = self.topic != config[CONF_TOPIC]
        self.topic = config[CONF_TOPIC]
        self.value_template = config[CONF_VALUE_TEMPLATE]

        # Unsubscribe+subscribe if this trigger is in use and topic has changed
        # If topic is same unsubscribe+subscribe will execute in the wrong order
        # because unsubscribe is done with help of async_create_task
        if topic_changed:
            for trig in self.trigger_instances:
                await trig.async_attach_trigger()

    def detach_trigger(self):
        """Remove MQTT device trigger."""
        # Mark trigger as unknown
        self.topic = None

        # Unsubscribe if this trigger is in use
        for trig in self.trigger_instances:
            if trig.remove:
                trig.remove()
                trig.remove = None


async def _update_device(hass, config_entry, config):
    """Update device registry."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    config_entry_id = config_entry.entry_id
    device_info = device_info_from_config(config[CONF_DEVICE])

    if config_entry_id is not None and device_info is not None:
        device_info["config_entry_id"] = config_entry_id
        device_registry.async_get_or_create(**device_info)


async def async_setup_trigger(hass, config, config_entry, discovery_data):
    """Set up the MQTT device trigger."""
    config = TRIGGER_DISCOVERY_SCHEMA(config)
    discovery_hash = discovery_data[ATTR_DISCOVERY_HASH]
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
            debug_info.remove_trigger_discovery_data(hass, discovery_hash)
            if discovery_id in hass.data[DEVICE_TRIGGERS]:
                device_trigger = hass.data[DEVICE_TRIGGERS][discovery_id]
                device_trigger.detach_trigger()
                clear_discovery_hash(hass, discovery_hash)
                remove_signal()
                await cleanup_device_registry(hass, device.id)
        else:
            # Non-empty payload: Update trigger
            _LOGGER.info("Updating trigger: %s", discovery_hash)
            debug_info.update_trigger_discovery_data(hass, discovery_hash, payload)
            config = TRIGGER_DISCOVERY_SCHEMA(payload)
            await _update_device(hass, config_entry, config)
            device_trigger = hass.data[DEVICE_TRIGGERS][discovery_id]
            await device_trigger.update_trigger(config, discovery_hash, remove_signal)
        async_dispatcher_send(hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None)

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
        async_dispatcher_send(hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None)
        return

    if DEVICE_TRIGGERS not in hass.data:
        hass.data[DEVICE_TRIGGERS] = {}
    if discovery_id not in hass.data[DEVICE_TRIGGERS]:
        hass.data[DEVICE_TRIGGERS][discovery_id] = Trigger(
            hass=hass,
            device_id=device.id,
            discovery_data=discovery_data,
            type=config[CONF_TYPE],
            subtype=config[CONF_SUBTYPE],
            topic=config[CONF_TOPIC],
            payload=config[CONF_PAYLOAD],
            qos=config[CONF_QOS],
            remove_signal=remove_signal,
            value_template=config[CONF_VALUE_TEMPLATE],
        )
    else:
        await hass.data[DEVICE_TRIGGERS][discovery_id].update_trigger(
            config, discovery_hash, remove_signal
        )
    debug_info.add_trigger_discovery_data(
        hass, discovery_hash, discovery_data, device.id
    )

    async_dispatcher_send(hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None)


async def async_device_removed(hass: HomeAssistant, device_id: str):
    """Handle the removal of a device."""
    triggers = await async_get_triggers(hass, device_id)
    for trig in triggers:
        device_trigger = hass.data[DEVICE_TRIGGERS].pop(trig[CONF_DISCOVERY_ID])
        if device_trigger:
            discovery_hash = device_trigger.discovery_data[ATTR_DISCOVERY_HASH]
            discovery_topic = device_trigger.discovery_data[ATTR_DISCOVERY_TOPIC]

            debug_info.remove_trigger_discovery_data(hass, discovery_hash)
            device_trigger.detach_trigger()
            clear_discovery_hash(hass, discovery_hash)
            device_trigger.remove_signal()
            mqtt.publish(
                hass,
                discovery_topic,
                "",
                retain=True,
            )


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device triggers for MQTT devices."""
    triggers: list[dict] = []

    if DEVICE_TRIGGERS not in hass.data:
        return triggers

    for discovery_id, trig in hass.data[DEVICE_TRIGGERS].items():
        if trig.device_id != device_id or trig.topic is None:
            continue

        trigger = {
            **MQTT_TRIGGER_BASE,
            "device_id": device_id,
            "type": trig.type,
            "subtype": trig.subtype,
            "discovery_id": discovery_id,
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
    if DEVICE_TRIGGERS not in hass.data:
        hass.data[DEVICE_TRIGGERS] = {}
    device_id = config[CONF_DEVICE_ID]
    discovery_id = config[CONF_DISCOVERY_ID]

    if discovery_id not in hass.data[DEVICE_TRIGGERS]:
        hass.data[DEVICE_TRIGGERS][discovery_id] = Trigger(
            hass=hass,
            device_id=device_id,
            discovery_data=None,
            remove_signal=None,
            type=config[CONF_TYPE],
            subtype=config[CONF_SUBTYPE],
            topic=None,
            payload=None,
            qos=None,
            value_template=None,
        )
    return await hass.data[DEVICE_TRIGGERS][discovery_id].add_trigger(
        action, automation_info
    )
