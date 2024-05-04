"""PG LAB Electronics integration."""

from __future__ import annotations

from pypglab.mqtt import Client, Sub_State, Subcribe_CallBack

from homeassistant.components import mqtt
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.components.mqtt.subscription import (
    async_prepare_subscribe_topics,
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, async_get_hass

from .const import DEVICE_ALREADY_DISCOVERED, DOMAIN
from .discovery import create_discovery

# The discovery instance
DISCOVERY_INSTANCE = "pglab_discovery_instance"

# Supported platforms
PLATFORMS = [
    Platform.SWITCH,
]


async def mqtt_publish_callback(
    topic: str, payload: str, qos: int, retain: bool
) -> None:
    """Define the call back for pglab module to publish a mqtt message."""
    hass = async_get_hass()
    await mqtt.async_publish(hass, topic, payload, qos, retain)


async def mqtt_subscribe_callback(
    sub_state: Sub_State,
    topic: str,
    callback_func: Subcribe_CallBack,
) -> Sub_State:
    """Define the call back for pglab module to subscribe to a mqtt topic."""

    async def discovery_message_received(msg: ReceiveMessage) -> None:
        callback_func(msg.topic, msg.payload)

    topics = {
        "pglab_subscribe_topic": {
            "topic": topic,
            "msg_callback": discovery_message_received,
        }
    }

    hass = async_get_hass()
    sub_state = async_prepare_subscribe_topics(hass, sub_state, topics)
    await async_subscribe_topics(hass, sub_state)
    return sub_state


async def mqtt_unsubscribe_callback(sub_state: Sub_State) -> None:
    """Define the call back for pglab module to unsubscribe to a topic."""
    hass = async_get_hass()
    async_unsubscribe_topics(hass, sub_state)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PG LAB Electronics integration from a config entry."""

    # create a mqtt client for pglab used for pglab python module
    pglab_mqtt = Client(
        mqtt_publish_callback, mqtt_subscribe_callback, mqtt_unsubscribe_callback
    )

    hass.data[DOMAIN] = {DEVICE_ALREADY_DISCOVERED: {}}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    pglab_discovery = await create_discovery(hass, entry, pglab_mqtt)
    hass.data[DOMAIN][DISCOVERY_INSTANCE] = pglab_discovery

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # cleanup platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    # stop pglab device discovery
    pglab_discovery = hass.data[DOMAIN][DISCOVERY_INSTANCE]
    if pglab_discovery:
        await pglab_discovery.stop(hass)

    hass.data.pop(DOMAIN)

    return True
