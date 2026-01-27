"""The iNELS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from inelsmqtt import InelsMqtt
from inelsmqtt.devices import Device
from inelsmqtt.discovery import InelsDiscovery

from homeassistant.components import mqtt as ha_mqtt
from homeassistant.components.mqtt import (
    ReceiveMessage,
    async_prepare_subscribe_topics,
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import LOGGER, PLATFORMS

type InelsConfigEntry = ConfigEntry[InelsData]


@dataclass
class InelsData:
    """Represents the data structure for INELS runtime data."""

    mqtt: InelsMqtt
    devices: list[Device]


async def async_setup_entry(hass: HomeAssistant, entry: InelsConfigEntry) -> bool:
    """Set up iNELS from a config entry."""

    async def mqtt_publish(topic: str, payload: str, qos: int, retain: bool) -> None:
        """Publish an MQTT message using the Home Assistant MQTT client."""
        await ha_mqtt.async_publish(hass, topic, payload, qos, retain)

    async def mqtt_subscribe(
        sub_state: dict[str, Any] | None,
        topic: str,
        callback_func: Callable[[str, str], None],
    ) -> dict[str, Any]:
        """Subscribe to MQTT topics using the Home Assistant MQTT client."""

        @callback
        def mqtt_message_received(msg: ReceiveMessage) -> None:
            """Handle iNELS mqtt messages."""
            # Payload is always str at runtime since we don't set encoding=None
            # HA uses UTF-8 by default
            callback_func(msg.topic, msg.payload)  # type: ignore[arg-type]

        topics = {
            "inels_subscribe_topic": {
                "topic": topic,
                "msg_callback": mqtt_message_received,
            }
        }

        sub_state = async_prepare_subscribe_topics(hass, sub_state, topics)
        await async_subscribe_topics(hass, sub_state)
        return sub_state

    async def mqtt_unsubscribe(sub_state: dict[str, Any]) -> None:
        async_unsubscribe_topics(hass, sub_state)

    if not await ha_mqtt.async_wait_for_mqtt_client(hass):
        LOGGER.error("MQTT integration not available")
        raise ConfigEntryNotReady("MQTT integration not available")

    inels_mqtt = InelsMqtt(mqtt_publish, mqtt_subscribe, mqtt_unsubscribe)
    devices: list[Device] = await InelsDiscovery(inels_mqtt).start()

    # If no devices are discovered, continue with the setup
    if not devices:
        LOGGER.info("No devices discovered")

    entry.runtime_data = InelsData(mqtt=inels_mqtt, devices=devices)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: InelsConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.mqtt.unsubscribe_topics()
    entry.runtime_data.mqtt.unsubscribe_listeners()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
