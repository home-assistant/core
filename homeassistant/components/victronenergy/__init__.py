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

from .const import CONF_BROKER, CONF_PORT, CONF_USERNAME, CONF_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]


class VictronMqttManager:
    """Manages MQTT connection and dynamic entity creation."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the MQTT manager."""
        self.hass = hass
        self.entry = entry
        self.client: mqtt.Client | None = None
        self._sensor_add_entities: Callable[[Sequence[Entity]], None] | None = None
        self._switch_add_entities: Callable[[Sequence[Entity]], None] | None = None
        self._number_add_entities: Callable[[Sequence[Entity]], None] | None = None
        self._pending_sensors: list[Entity] = []
        self._pending_switches: list[Entity] = []
        self._pending_numbers: list[Entity] = []
        self._connected = asyncio.Event()
        self._subscribed_topics: set[str] = set()
        self._topic_entity_map: dict[str, list[Entity]] = {}
        self._entity_registry: dict[str, Entity] = {}  # Track entities by unique_id
        self._unique_id: str | None = None
        self._keepalive_task_started = False
        self._platforms_setup_complete = False
        self._initial_keepalive_sent = False

    def set_sensor_add_entities(
        self, add_entities: Callable[[Sequence[Entity]], None]
    ) -> None:
        """Set the callback to add sensor entities."""
        self._sensor_add_entities = add_entities
        if self._pending_sensors:
            self._sensor_add_entities(self._pending_sensors)
            self._pending_sensors = []

    def set_switch_add_entities(
        self, add_entities: Callable[[Sequence[Entity]], None]
    ) -> None:
        """Set the callback to add switch entities."""
        self._switch_add_entities = add_entities
        if self._pending_switches:
            self._switch_add_entities(self._pending_switches)
            self._pending_switches = []

    def set_number_add_entities(
        self, add_entities: Callable[[Sequence[Entity]], None]
    ) -> None:
        """Set the callback to add number entities."""
        self._number_add_entities = add_entities
        if self._pending_numbers:
            self._number_add_entities(self._pending_numbers)
            self._pending_numbers = []

    def start(self) -> None:
        """Start the MQTT client in a background thread and prepare keepalive publishing."""
        broker = self.entry.data[CONF_BROKER]
        port = self.entry.data[CONF_PORT]
        username = self.entry.data.get(CONF_USERNAME)
        token = self.entry.data.get("token")  # Use token instead of password
        unique_id = self.entry.unique_id

        _LOGGER.info("Starting MQTT connection to %s:%s", broker, port)
        _LOGGER.info("Username: %s, Token available: %s", username, bool(token))
        _LOGGER.info("Unique ID: %s", unique_id)

        client = mqtt.Client()

        # Set up authentication
        if username and token:
            client.username_pw_set(username, token)
            _LOGGER.info("MQTT authentication configured with token")
        else:
            _LOGGER.info("No authentication configured (anonymous MQTT)")

        # Configure TLS for secure MQTT (port 8883)
        if port == 8883:
            import ssl
            client.tls_set(ca_certs=None, certfile=None, keyfile=None,
                          cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS,
                          ciphers=None)
            client.tls_insecure_set(True)  # Allow self-signed certificates
            _LOGGER.info("TLS configured for secure MQTT")

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
        _LOGGER.info("MQTT connection callback - result code: %s", rc)
        if rc == 0:
            _LOGGER.info(
                "Successfully connected to MQTT broker at %s:%d",
                self.entry.data[CONF_BROKER],
                self.entry.data[CONF_PORT],
            )
            # Subscribe to all discovery topics
            result = client.subscribe("homeassistant/#")
            _LOGGER.info("Subscribed to homeassistant/# discovery topics, result: %s", result)

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
                "Failed to connect to MQTT broker - result code %s: %s", rc, mqtt.connack_string(rc)
            )
            if rc == 5:
                _LOGGER.error("Connection refused: Not authorized. Check username/token configuration.")
            elif rc == 4:
                _LOGGER.error("Connection refused: Bad username or password.")
            elif rc == 3:
                _LOGGER.error("Connection refused: Server unavailable.")
            elif rc == 2:
                _LOGGER.error("Connection refused: Bad client identifier.")
            elif rc == 1:
                _LOGGER.error("Connection refused: Wrong protocol version.")

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
        from .switch import MQTTDiscoveredSwitch
        from .number import MQTTDiscoveredNumber

        # New format: data contains "components" (dict of sensors/switches/numbers) and "device"
        components = data.get("components")
        device_info = data.get("device")
        if not components or not device_info:
            _LOGGER.debug("Invalid discovery message: missing components or device")
            return
        new_sensors = []
        new_switches = []
        new_numbers = []
        updated_entities = []

        for unique_id, component_cfg in components.items():
            # Attach device info to each component config
            component_cfg = dict(component_cfg)  # shallow copy
            component_cfg["device"] = device_info
            platform = component_cfg.get("platform")

            # Check if entity already exists
            existing_entity = self._entity_registry.get(unique_id)
            if existing_entity and hasattr(existing_entity, 'update_config'):
                # Update existing entity configuration
                existing_entity.update_config(component_cfg)
                updated_entities.append(existing_entity)
                _LOGGER.debug(
                    "Updated existing entity %s with new configuration", unique_id
                )
                # Trigger state update to reflect any changes
                existing_entity.async_write_ha_state()
            else:
                # Create new entity
                if platform == "sensor":
                    entity = MQTTDiscoveredSensor(component_cfg, unique_id)
                    new_sensors.append(entity)
                    self._entity_registry[unique_id] = entity
                elif platform == "switch":
                    entity = MQTTDiscoveredSwitch(component_cfg, unique_id)
                    new_switches.append(entity)
                    self._entity_registry[unique_id] = entity
                elif platform == "number":
                    entity = MQTTDiscoveredNumber(component_cfg, unique_id)
                    new_numbers.append(entity)
                    self._entity_registry[unique_id] = entity

        if new_sensors:
            if self._sensor_add_entities:
                self._sensor_add_entities(new_sensors)
            else:
                self._pending_sensors.extend(new_sensors)

        if new_switches:
            if self._switch_add_entities:
                self._switch_add_entities(new_switches)
            else:
                self._pending_switches.extend(new_switches)

        if new_numbers:
            if self._number_add_entities:
                self._number_add_entities(new_numbers)
            else:
                self._pending_numbers.extend(new_numbers)

        if updated_entities:
            _LOGGER.info(
                "Updated configuration for %d existing entities", len(updated_entities)
            )

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

    def set_platforms_setup_complete(self) -> None:
        """Mark that all platforms have been set up and send initial keepalive."""
        self._platforms_setup_complete = True
        self.hass.loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self._send_initial_keepalive())
        )

    async def _send_initial_keepalive(self) -> None:
        """Send initial keepalive without suppress-republish to trigger data republishing."""
        if self._initial_keepalive_sent or not self._unique_id:
            return

        # Wait for MQTT connection if not ready yet
        await self._connected.wait()

        if self.client is not None:
            topic = f"R/{self._unique_id}/keepalive"
            # Send keepalive without suppress-republish to trigger republishing
            payload = json.dumps({"keepalive-options": []})
            self.client.publish(topic, payload=payload, qos=0, retain=False)
            _LOGGER.info(
                "Published initial republish keepalive to topic: %s with payload: %s",
                topic,
                payload,
            )
            self._initial_keepalive_sent = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Victron Energy from a config entry."""
    try:
        manager = VictronMqttManager(hass, entry)
        hass.data.setdefault(DOMAIN, {})["manager"] = manager
        entry.runtime_data = manager
        manager.start()
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

        # Signal that all platforms are set up and ready
        manager.set_platforms_setup_complete()

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
