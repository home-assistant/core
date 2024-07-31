"""PG LAB Electronics integration."""

from __future__ import annotations

from pypglab.mqtt import (
    Client as PyPGLabMqttClient,
    Sub_State as PyPGLabSubState,
    Subcribe_CallBack as PyPGLabSubscribeCallBack,
)

from homeassistant.components import mqtt
from homeassistant.components.mqtt import (
    ReceiveMessage,
    async_prepare_subscribe_topics,
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .discovery import PGLabDiscovery, create_discovery

type PGLABConfigEntry = ConfigEntry[PGLabDiscovery]


async def async_setup_entry(hass: HomeAssistant, entry: PGLABConfigEntry) -> bool:
    """Set up PG LAB Electronics integration from a config entry."""

    async def mqtt_publish(topic: str, payload: str, qos: int, retain: bool) -> None:
        """Publish an MQTT message using the Home Assistant MQTT client."""
        await mqtt.async_publish(hass, topic, payload, qos, retain)

    async def mqtt_subscribe(
        sub_state: PyPGLabSubState, topic: str, callback_func: PyPGLabSubscribeCallBack
    ) -> PyPGLabSubState:
        """Subscribe to MQTT topics using the Home Assistant MQTT client."""

        @callback
        def discovery_message_received(msg: ReceiveMessage) -> None:
            """Handle PGLab discovery messages."""
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

    # Create an MQTT client for PGLab used for PGLab python module.
    pglab_mqtt = PyPGLabMqttClient(mqtt_publish, mqtt_subscribe, mqtt_unsubscribe)

    # Setup PGLab device discovery.
    await create_discovery(hass, entry, pglab_mqtt)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PGLABConfigEntry) -> bool:
    """Unload a config entry."""

    # Stop PGLab device discovery.
    pglab_discovery = entry.runtime_data
    await pglab_discovery.stop(hass, entry)

    return True
