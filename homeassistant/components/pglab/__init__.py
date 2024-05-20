"""PG LAB Electronics integration."""

from __future__ import annotations

from pypglab.mqtt import (
    Client as PyPGLabMqttClient,
    Sub_State as PyPGLabSubState,
    Subcribe_CallBack as PyPGLaSubscribeCallBack,
)

from homeassistant.components import mqtt
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.components.mqtt.subscription import (
    async_prepare_subscribe_topics,
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from homeassistant.core import HomeAssistant

from .discovery import PGLABConfigEntry, create_discovery


async def async_setup_entry(hass: HomeAssistant, entry: PGLABConfigEntry) -> bool:
    """Set up PG LAB Electronics integration from a config entry."""

    # define the call back for pglab  module to publish a mqtt message
    async def mqtt_publish(topic: str, payload: str, qos: int, retain: bool) -> None:
        await mqtt.async_publish(hass, topic, payload, qos, retain)

    # define the call back for pglab module to subscribe to a mqtt message
    async def mqtt_subscribe(
        sub_state: PyPGLabSubState, topic: str, callback_func: PyPGLaSubscribeCallBack
    ) -> PyPGLabSubState:
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

    async def mqtt_unsubscribe(sub_state: PyPGLabSubState) -> None:
        async_unsubscribe_topics(hass, sub_state)

    # create a mqtt client for pglab used for pglab python module
    pglab_mqtt = PyPGLabMqttClient(mqtt_publish, mqtt_subscribe, mqtt_unsubscribe)

    # setup PG LAB device discovery
    await create_discovery(hass, entry, pglab_mqtt)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PGLABConfigEntry) -> bool:
    """Unload a config entry."""

    # stop pglab device discovery
    pglab_discovery = entry.runtime_data
    await pglab_discovery.stop(hass, entry)

    return True
