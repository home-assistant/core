"""Airzone MQTT integration."""

from __future__ import annotations

from datetime import datetime
import logging

from airzone_mqtt.const import TZ_UTC
from airzone_mqtt.mqttapi import AirzoneMqttApi

from homeassistant.components import mqtt
from homeassistant.components.mqtt import PublishPayloadType, ReceiveMessage
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .const import CONF_MQTT_TOPIC
from .coordinator import AirzoneMqttConfigEntry, AirzoneUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirzoneMqttConfigEntry,
) -> bool:
    """Set up Airzone MQTT from a config entry."""

    airzone = AirzoneMqttApi(entry.data[CONF_MQTT_TOPIC])

    async def mqtt_publish(
        topic: str,
        payload: PublishPayloadType,
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        """Publish MQTT payload."""
        await mqtt.async_publish(
            hass=hass,
            topic=topic,
            payload=payload,
            qos=qos,
            retain=retain,
        )

    @callback
    def mqtt_callback(msg: ReceiveMessage) -> None:
        """Pass MQTT payload to Airzone library."""
        airzone.msg_callback(
            topic_str=msg.topic,
            payload=str(msg.payload),
            dt=datetime.fromtimestamp(msg.timestamp, tz=TZ_UTC),
        )

    airzone.mqtt_publish = mqtt_publish

    entry.async_on_unload(
        await mqtt.async_subscribe(
            hass,
            f"{entry.data[CONF_MQTT_TOPIC]}/v1/#",
            mqtt_callback,
        )
    )

    coordinator = AirzoneUpdateCoordinator(hass, entry, airzone)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: AirzoneMqttConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
