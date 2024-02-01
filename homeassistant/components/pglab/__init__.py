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
from homeassistant.core import HomeAssistant

from .const import DEVICE_ALREADY_DISCOVERED, DISCONNECT_COMPONENT, DISCOVERY_INSTANCE
from .discovery import CreateDiscovery

PLATFORMS = [
    Platform.COVER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PG LAB Electronics integration from a config entry."""

    # define the call back for pglab  module to publish a mqtt message
    async def mqtt_publish(
        topic: str, payload: str, qos: int | None = 0, retain: bool | None = False
    ) -> None:
        await mqtt.async_publish(hass, topic, payload, qos, retain)

    # define the call back for pglab module to subscribe to a mqtt message
    async def mqtt_subscribe(
        sub_state: Sub_State, topic: str, callback_func: Subcribe_CallBack
    ) -> Sub_State:
        async def discovery_message_received(msg: ReceiveMessage) -> None:
            callback_func(msg.topic, msg.payload)

        topics = {
            "pglab_subscribe_topic": {
                "topic": topic,
                "msg_callback": discovery_message_received,
            }
        }

        sub_state = async_prepare_subscribe_topics(hass, sub_state, topics)
        await async_subscribe_topics(hass, sub_state)
        return sub_state

    async def mqtt_unsubscribe(sub_state: Sub_State) -> None:
        async_unsubscribe_topics(hass, sub_state)

    # create a mqtt client for pglab used for pglab python module
    pglab_mqtt = Client(mqtt_publish, mqtt_subscribe, mqtt_unsubscribe)

    # preparing the discovery module
    hass.data[DEVICE_ALREADY_DISCOVERED] = {}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    pglab_discovery = await CreateDiscovery(hass, entry, pglab_mqtt)
    hass.data[DISCOVERY_INSTANCE] = pglab_discovery

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # cleanup platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    # stop pglab device discovery
    pglab_discovery = hass.data[DISCOVERY_INSTANCE]
    if pglab_discovery:
        await pglab_discovery.stop(hass)
    hass.data.pop(DISCOVERY_INSTANCE)

    # cleanup subscriptions
    for platform in PLATFORMS:
        hass.data.pop(DISCONNECT_COMPONENT[platform])()

    return True
