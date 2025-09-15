"""Victron Energy integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
import json
import logging
from typing import Any

import paho.mqtt.client as mqtt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.entity import Entity

from .const import CONF_BROKER, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.SENSOR]


class VictronMqttManager:
    """Manages MQTT connection and dynamic entity creation."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the MQTT manager."""
        self.hass = hass
        self.entry = entry
        self.client: mqtt.Client | None = None
        self._sensor_add_entities: Callable[[Sequence[Entity]], None] | None = None
        self._pending_sensors: list[Entity] = []
        self._connected = asyncio.Event()
        self._subscribed_topics: set[str] = set()
        self._topic_entity_map: dict[str, list[Entity]] = {}
        self._unique_id: str | None = None
        self._keepalive_task_started = False

    def set_sensor_add_entities(
        self, add_entities: Callable[[Sequence[Entity]], None]
    ) -> None:
        """Set the callback to add sensor entities."""
        self._sensor_add_entities = add_entities
        if self._pending_sensors:
            self._sensor_add_entities(self._pending_sensors)
            self._pending_sensors = []

    def start(self) -> None:
        """Start the MQTT client in a background thread and prepare keepalive publishing."""
        broker = self.entry.data[CONF_BROKER]
        port = self.entry.data[CONF_PORT]
        username = self.entry.data.get(CONF_USERNAME)
        password = self.entry.data.get(CONF_PASSWORD)
        unique_id = self.entry.unique_id
        _LOGGER.debug("unique_id resolved to: %s", unique_id)

        client = mqtt.Client()
        if username and password:
            client.username_pw_set(username, password)
        client.on_connect = self._on_connect
        client.on_message = self._on_message

        self.client = client
        self._unique_id = unique_id
        # Run the MQTT client in a background thread
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self._run_client, broker, port)

    def _run_client(self, broker: str, port: int) -> None:
        """Run the MQTT client loop."""
        _LOGGER.debug("Connecting to MQTT broker at %s:%d", broker, port)
        if self.client is not None:
            self.client.connect(broker, port, 60)
            _LOGGER.debug("Starting MQTT client loop")
            self.client.loop_forever()

    def _on_connect(self, client, userdata, flags, rc) -> None:
        """Handle MQTT connection."""
        if rc == 0:
            _LOGGER.info(
                "Connected to MQTT broker at %s:%d",
                self.entry.data[CONF_BROKER],
                self.entry.data[CONF_PORT],
            )
            # Subscribe to all discovery topics
            client.subscribe("homeassistant/#")
            # Re-subscribe to all state topics
            for topic in self._subscribed_topics:
                client.subscribe(topic)
                _LOGGER.debug("Re-Subscribed to MQTT topic: %s", topic)
            self._connected.set()
            # Publish initial keepalive and start periodic task
            if self._unique_id and not self._keepalive_task_started:
                topic = f"R/{self._unique_id}/keepalive"
                client.publish(topic, payload="", qos=0, retain=False)
                _LOGGER.debug("Published initial keepalive to topic: %s", topic)
                # Schedule keepalive task on main event loop
                self.hass.loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(self._publish_keepalive_task())
                )
                self._keepalive_task_started = True
                _LOGGER.debug(
                    "Started keepalive task for unique ID: %s", self._unique_id
                )
            else:
                _LOGGER.debug(
                    "Keepalive task already started for unique ID: %s", self._unique_id
                )
        else:
            _LOGGER.error(
                "Failed to connect to MQTT broker: %s", mqtt.connack_string(rc)
            )

    async def _publish_keepalive_task(self) -> None:
        """Publish keepalive JSON payload every 30 seconds."""
        topic = f"R/{self._unique_id}/keepalive"
        while True:
            if self.client is not None:
                payload = json.dumps({"keepalive-options": ["suppress-republish"]})
                self.client.publish(topic, payload=payload, qos=0, retain=False)
                _LOGGER.debug(
                    "Published periodic keepalive to topic: %s with payload: %s",
                    topic,
                    payload,
                )
            await asyncio.sleep(30)

    def _on_message(self, client, userdata, msg) -> None:
        """Handle all MQTT messages."""
        _LOGGER.debug("Global on_message: %s %s", msg.topic, msg.payload)
        entities = self._topic_entity_map.get(msg.topic)
        if entities:
            for entity in entities:
                if hasattr(entity, "handle_mqtt_message"):
                    entity.handle_mqtt_message(msg)
        else:
            try:
                payload = msg.payload.decode()
                data = json.loads(payload)
                topic = msg.topic
                self.hass.loop.call_soon_threadsafe(
                    asyncio.create_task, self._handle_discovery_message(topic, data)
                )
            except json.JSONDecodeError as err:
                _LOGGER.debug("Failed to process MQTT message JSON: %s", err)
            except Exception as err:
                _LOGGER.debug("Unexpected error processing MQTT message: %s", err)
                raise err from err

    async def _handle_discovery_message(self, topic: str, data: dict[str, Any]) -> None:
        """Handle a Home Assistant MQTT discovery message."""
        # Import here to avoid circular imports
        # pylint: disable=import-outside-toplevel
        from .sensor import MQTTDiscoveredSensor

        # New format: data contains "components" (dict of sensors) and "device"
        components = data.get("components")
        device_info = data.get("device")
        if not components or not device_info:
            _LOGGER.debug("Invalid discovery message: missing components or device")
            return
        new_entities = []
        for unique_id, sensor_cfg in components.items():
            # Attach device info to each sensor config
            sensor_cfg = dict(sensor_cfg)  # shallow copy
            sensor_cfg["device"] = device_info
            if sensor_cfg.get("platform") == "sensor":
                entity = MQTTDiscoveredSensor(sensor_cfg, unique_id)
                new_entities.append(entity)
        if new_entities:
            if self._sensor_add_entities:
                self._sensor_add_entities(new_entities)
            else:
                self._pending_sensors.extend(new_entities)

    def register_entity_for_topic(self, topic: str, entity: Entity) -> None:
        """Register an entity for a topic."""
        if topic not in self._topic_entity_map:
            self._topic_entity_map[topic] = []
        self._topic_entity_map[topic].append(entity)

    def subscribe_topic(self, topic: str) -> None:
        """Subscribe to a topic."""
        self._subscribed_topics.add(topic)
        if self.client:
            self.client.subscribe(topic)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Victron Energy from a config entry."""
    try:
        manager = VictronMqttManager(hass, entry)
        hass.data.setdefault(DOMAIN, {})["manager"] = manager
        entry.runtime_data = manager
        manager.start()
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    except OSError as err:
        _LOGGER.debug("MQTT connection failed: %s", err)
        raise ConfigEntryNotReady from err
    except Exception as err:
        _LOGGER.debug("Unexpected setup error: %s", err)
        raise ConfigEntryError from err
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    manager: VictronMqttManager = hass.data[DOMAIN].pop("manager")
    if manager.client:
        manager.client.disconnect()
        manager.client.loop_stop()
    return True
