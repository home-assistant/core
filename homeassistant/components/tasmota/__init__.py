"""Support for MQTT message handling."""
import logging

from hatasmota.const import (
    CONF_ID,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_NAME,
    CONF_SW_VERSION,
)
from hatasmota.discovery import clear_discovery_topic
from hatasmota.mqtt import TasmotaMQTTClient

from homeassistant.components import mqtt
from homeassistant.components.mqtt.subscription import (
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from . import discovery
from .const import CONF_DISCOVERY_PREFIX, DOMAIN
from .discovery import TASMOTA_DISCOVERY_DEVICE

# from typing import Optional


_LOGGER = logging.getLogger(__name__)

DEVICE_IDS = "tasmota_devices"


async def async_setup(hass: HomeAssistantType, config: dict):
    """Set up the Tasmota component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Tasmota from a config entry."""
    hass.data[DEVICE_IDS] = {}

    def _publish(*args, **kwds):
        mqtt.async_publish(hass, *args, **kwds)

    async def _subscribe_topics(sub_state, topics):
        # Optionally mark message handlers as callback
        for topic in topics.values():
            if "msg_callback" in topic and "event_loop_safe" in topic:
                topic["msg_callback"] = callback(topic["msg_callback"])
        return await async_subscribe_topics(hass, sub_state, topics)

    async def _unsubscribe_topics(sub_state):
        return await async_unsubscribe_topics(hass, sub_state)

    tasmota_mqtt = TasmotaMQTTClient(_publish, _subscribe_topics, _unsubscribe_topics)

    discovery_prefix = entry.data[CONF_DISCOVERY_PREFIX]
    await discovery.async_start(hass, discovery_prefix, entry, tasmota_mqtt)

    async def async_device_removed(event):
        """Handle the removal of a device."""
        if event.data["action"] != "remove":
            return
        serial_number = hass.data[DEVICE_IDS].get(event.data["device_id"])
        if not serial_number:
            return

        clear_discovery_topic(
            serial_number, entry.data[CONF_DISCOVERY_PREFIX], tasmota_mqtt
        )

    async def async_discover_device(config, serial_number):
        """Discover and add a Tasmota device."""
        await async_setup_device(hass, serial_number, config, entry)

    async_dispatcher_connect(hass, TASMOTA_DISCOVERY_DEVICE, async_discover_device)
    hass.bus.async_listen(EVENT_DEVICE_REGISTRY_UPDATED, async_device_removed)

    return True


async def _remove_device(hass, serial_number):
    """Remove device from device registry."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_device({(DOMAIN, serial_number)}, None)

    if device is None:
        return

    _LOGGER.info("Removing tasmota device %s", serial_number)
    device_registry.async_remove_device(device.id)


async def _update_device(hass, config_entry, config):
    """Add or update device registry."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    config_entry_id = config_entry.entry_id
    device_info = {"identifiers": {(DOMAIN, config[CONF_ID])}}
    device_info["manufacturer"] = config[CONF_MANUFACTURER]
    device_info["model"] = config[CONF_MODEL]
    device_info["name"] = config[CONF_NAME]
    device_info["sw_version"] = config[CONF_SW_VERSION]

    device_info["config_entry_id"] = config_entry_id
    _LOGGER.debug("Adding or updating tasmota device %s", config[CONF_ID])
    device = device_registry.async_get_or_create(**device_info)
    hass.data[DEVICE_IDS][device.id] = config[CONF_ID]


async def async_setup_device(hass, serial_number, config, config_entry):
    """Set up the Tasmota device."""
    if not config:
        await _remove_device(hass, serial_number)
    else:
        await _update_device(hass, config_entry, config)
