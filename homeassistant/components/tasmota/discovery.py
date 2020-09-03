"""Support for MQTT discovery."""
import asyncio
import json
import logging
import re

from hatasmota.const import CONF_RELAY
from hatasmota.discovery import (
    TasmotaDiscoveryMsg,
    get_device_config,
    get_entities_for_platform,
    has_entities_with_platform,
)

from homeassistant.components import mqtt
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import HomeAssistantType

from .const import ATTR_DISCOVERY_TOPIC, DOMAIN

_LOGGER = logging.getLogger(__name__)

TOPIC_MATCHER = re.compile(r"(?P<serial_number>[A-Z0-9_-]+)\/config")

SUPPORTED_COMPONENTS = {
    "switch": CONF_RELAY,
}

ALREADY_DISCOVERED = "tasmota_discovered_components"
CONFIG_ENTRY_IS_SETUP = "tasmota_config_entry_is_setup"
DATA_CONFIG_ENTRY_LOCK = "tasmota_config_entry_lock"
DISCOVERY_UNSUBSCRIBE = "tasmota_discovery_unsubscribe"
TASMOTA_DISCOVERY_DEVICE = "tasmota_discovery_device"
TASMOTA_DISCOVERY_ENTITY_NEW = "tasmota_discovery_entity_new_{}"
TASMOTA_DISCOVERY_ENTITY_UPDATED = "tasmota_discovery_entity_updated_{}_{}_{}"


def clear_discovery_hash(hass, discovery_hash):
    """Clear entry in ALREADY_DISCOVERED list."""
    del hass.data[ALREADY_DISCOVERED][discovery_hash]


def set_discovery_hash(hass, discovery_hash):
    """Set entry in ALREADY_DISCOVERED list."""
    hass.data[ALREADY_DISCOVERED][discovery_hash] = {}


async def async_start(
    hass: HomeAssistantType, discovery_topic, config_entry=None
) -> bool:
    """Start MQTT Discovery."""

    async def async_discovery_message_received(msg):
        """Process the received message."""
        payload = msg.payload
        topic = msg.topic
        topic_trimmed = topic.replace(f"{discovery_topic}/", "", 1)
        match = TOPIC_MATCHER.match(topic_trimmed)

        if not match:
            return

        (serial_number,) = match.groups()

        if payload:
            try:
                payload = TasmotaDiscoveryMsg(json.loads(payload))
            except ValueError:
                _LOGGER.warning("Unable to parse JSON %s: '%s'", serial_number, payload)
                return
        else:
            payload = {}

        if payload:
            # Attach MQTT topic to the payload, used for debug prints
            setattr(payload, "__configuration_source__", f"Tasmota (topic: '{topic}')")
            discovery_data = {
                ATTR_DISCOVERY_TOPIC: topic,
            }
            setattr(payload, "discovery_data", discovery_data)

        if ALREADY_DISCOVERED not in hass.data:
            hass.data[ALREADY_DISCOVERED] = {}

        _LOGGER.info("Discovered tasmota device: %s", serial_number)
        device_config = get_device_config(payload)
        async_dispatcher_send(
            hass, TASMOTA_DISCOVERY_DEVICE, device_config, serial_number, payload
        )

        async with hass.data[DATA_CONFIG_ENTRY_LOCK]:
            for component, component_key in SUPPORTED_COMPONENTS.items():
                if not has_entities_with_platform(payload, component_key):
                    continue
                config_entries_key = f"{component}.tasmota"
                if config_entries_key not in hass.data[CONFIG_ENTRY_IS_SETUP]:
                    await hass.config_entries.async_forward_entry_setup(
                        config_entry, component
                    )
                    hass.data[CONFIG_ENTRY_IS_SETUP].add(config_entries_key)

        for component, component_key in SUPPORTED_COMPONENTS.items():
            entities = get_entities_for_platform(payload, component_key)
            for (idx, config) in enumerate(entities):
                discovery_hash = (serial_number, component, idx)
                if not config:
                    # Entity disabled, clean up entity registry
                    entity_registry = (
                        await hass.helpers.entity_registry.async_get_registry()
                    )
                    unique_id = "{}_{}_{}".format(*discovery_hash)
                    entity_id = entity_registry.async_get_entity_id(
                        component, DOMAIN, unique_id
                    )
                    if entity_id:
                        _LOGGER.info(
                            "Removing entity: %s %s", component, discovery_hash
                        )
                        entity_registry.async_remove(entity_id)
                    continue

                if discovery_hash in hass.data[ALREADY_DISCOVERED]:
                    _LOGGER.info(
                        "Entity already added, sending update: %s %s",
                        component,
                        discovery_hash,
                    )
                    async_dispatcher_send(
                        hass,
                        TASMOTA_DISCOVERY_ENTITY_UPDATED.format(*discovery_hash),
                        config,
                    )
                else:
                    _LOGGER.info("Adding new entity: %s %s", component, discovery_hash)
                    hass.data[ALREADY_DISCOVERED][discovery_hash] = None
                    async_dispatcher_send(
                        hass,
                        TASMOTA_DISCOVERY_ENTITY_NEW.format(component),
                        config,
                        discovery_hash,
                        payload,
                    )

    hass.data[DATA_CONFIG_ENTRY_LOCK] = asyncio.Lock()
    hass.data[CONFIG_ENTRY_IS_SETUP] = set()

    hass.data[DISCOVERY_UNSUBSCRIBE] = await mqtt.async_subscribe(
        hass, f"{discovery_topic}/#", async_discovery_message_received, 0
    )

    return True


async def async_stop(hass: HomeAssistantType) -> bool:
    """Stop Tasmota discovery."""
    if DISCOVERY_UNSUBSCRIBE in hass.data and hass.data[DISCOVERY_UNSUBSCRIBE]:
        hass.data[DISCOVERY_UNSUBSCRIBE]()
        hass.data[DISCOVERY_UNSUBSCRIBE] = None
