"""The Tasmota integration."""
import asyncio
import logging

from hatasmota.mqtt import TasmotaMQTTClient

from homeassistant.components import mqtt, websocket_api
from homeassistant.components.mqtt.subscription import (
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import async_entries_for_config_entry
from homeassistant.helpers.typing import HomeAssistantType

from . import device_automation
from .const import DATA_REMOVE_DISCOVER_COMPONENT, DATA_UNSUB, PLATFORMS
from .device import (
    async_start_device_discovery,
    async_stop_device_discovery,
    websocket_get_device,
    websocket_remove_device,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: dict):
    """Set up the Tasmota component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Tasmota from a config entry."""
    websocket_api.async_register_command(hass, websocket_remove_device)
    websocket_api.async_register_command(hass, websocket_get_device)
    hass.data[DATA_UNSUB] = []

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

    async def start_platforms():
        await device_automation.async_setup_entry(hass, entry)
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, component)
                for component in PLATFORMS
            ]
        )

        await async_start_device_discovery(hass, entry, tasmota_mqtt)

    hass.async_create_task(start_platforms())
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""

    # cleanup platforms
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if not unload_ok:
        return False

    # disable device discovery
    await async_stop_device_discovery(hass)

    # cleanup subscriptions
    for unsub in hass.data[DATA_UNSUB]:
        unsub()
    hass.data.pop(DATA_REMOVE_DISCOVER_COMPONENT.format("device_automation"))()
    for component in PLATFORMS:
        hass.data.pop(DATA_REMOVE_DISCOVER_COMPONENT.format(component))()

    # deattach device triggers
    device_registry = await hass.helpers.device_registry.async_get_registry()
    devices = async_entries_for_config_entry(device_registry, entry.entry_id)
    for device in devices:
        await device_automation.async_remove_automations(hass, device.id)

    return True
