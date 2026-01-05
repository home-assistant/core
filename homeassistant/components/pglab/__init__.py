"""PG LAB Electronics integration."""

from __future__ import annotations

from pypglab.mqtt import (
    Client as PyPGLabMqttClient,
    Sub_State as PyPGLabSubState,
    Subscribe_CallBack as PyPGLabSubscribeCallBack,
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
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, LOGGER
from .discovery import PGLabDiscovery

type PGLabConfigEntry = ConfigEntry[PGLabDiscovery]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: PGLabConfigEntry
) -> bool:
    """Set up PG LAB Electronics integration from a config entry."""

    async def mqtt_publish(topic: str, payload: str, qos: int, retain: bool) -> None:
        """Publish an MQTT message using the Home Assistant MQTT client."""
        await mqtt.async_publish(hass, topic, payload, qos, retain)

    async def mqtt_subscribe(
        sub_state: PyPGLabSubState, topic: str, callback_func: PyPGLabSubscribeCallBack
    ) -> PyPGLabSubState:
        """Subscribe to MQTT topics using the Home Assistant MQTT client."""

        @callback
        def mqtt_message_received(msg: ReceiveMessage) -> None:
            """Handle PGLab mqtt messages."""
            callback_func(msg.topic, msg.payload)

        topics = {
            "pglab_subscribe_topic": {
                "topic": topic,
                "msg_callback": mqtt_message_received,
            }
        }

        sub_state = async_prepare_subscribe_topics(hass, sub_state, topics)
        await async_subscribe_topics(hass, sub_state)
        return sub_state

    async def mqtt_unsubscribe(sub_state: PyPGLabSubState) -> None:
        async_unsubscribe_topics(hass, sub_state)

    if not await mqtt.async_wait_for_mqtt_client(hass):
        LOGGER.error("MQTT integration not available")
        raise ConfigEntryNotReady("MQTT integration not available")

    # Create an MQTT client for PGLab used for PGLab python module.
    pglab_mqtt = PyPGLabMqttClient(mqtt_publish, mqtt_subscribe, mqtt_unsubscribe)

    # Setup PGLab device discovery.
    config_entry.runtime_data = PGLabDiscovery()

    # Start to discovery PG Lab devices.
    await config_entry.runtime_data.start(hass, pglab_mqtt, config_entry)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: PGLabConfigEntry
) -> bool:
    """Unload a config entry."""

    # Stop PGLab device discovery.
    pglab_discovery = config_entry.runtime_data
    await pglab_discovery.stop(hass, config_entry)

    return True
