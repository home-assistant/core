"""Victron Energy integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
from typing import Any

import paho.mqtt.client as mqtt

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.template import Template

from .const import CONF_BROKER, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.SENSOR]


class VictronMqttManager:
    """Manages MQTT connection and dynamic entity creation."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the MQTT manager."""
        self.hass = hass
        self.entry = entry
        self.client = None
        self._sensor_add_entities: Callable[[list[Entity]], None] | None = None
        self._pending_sensors: list[MQTTDiscoveredSensor] = []
        self._connected = asyncio.Event()
        self._subscribed_topics: set[str] = set()
        self._topic_entity_map: dict[str, list[MQTTDiscoveredSensor]] = {}

    def set_sensor_add_entities(
        self, add_entities: Callable[[list[Entity]], None]
    ) -> None:
        """Set the callback to add sensor entities."""
        self._sensor_add_entities = add_entities
        if self._pending_sensors:
            self._sensor_add_entities(self._pending_sensors)
            self._pending_sensors.clear()

    def start(self) -> None:
        """Start the MQTT client in a background thread."""
        broker = self.entry.data[CONF_BROKER]
        port = self.entry.data[CONF_PORT]
        username = self.entry.data.get(CONF_USERNAME)
        password = self.entry.data.get(CONF_PASSWORD)

        client = mqtt.Client()
        if username and password:
            client.username_pw_set(username, password)
        client.on_connect = self._on_connect
        client.on_message = self._on_message

        self.client = client
        # Run the MQTT client in a background thread
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self._run_client, broker, port)

    def _run_client(self, broker: str, port: int) -> None:
        """Run the MQTT client loop."""
        _LOGGER.debug("Connecting to MQTT broker at %s:%d", broker, port)
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
            self._connected.set()
        else:
            _LOGGER.error(
                "Failed to connect to MQTT broker: %s", mqtt.connack_string(rc)
            )

    def subscribe_topic(self, topic: str, callback) -> None:
        """Subscribe to a topic and remember it for reconnects."""
        _LOGGER.debug("Subscribing to topic: %s", topic)
        self._subscribed_topics.add(topic)
        self.client.message_callback_add(topic, callback)
        self.client.subscribe(topic)

    def register_entity_for_topic(
        self, topic: str, entity: MQTTDiscoveredSensor
    ) -> None:
        """Register an entity for a topic."""
        if topic not in self._topic_entity_map:
            self._topic_entity_map[topic] = []
        self._topic_entity_map[topic].append(entity)
        self._subscribed_topics.add(topic)
        self.client.subscribe(topic)

    def _on_message(self, client, userdata, msg) -> None:
        """Handle all MQTT messages."""
        _LOGGER.debug("Global on_message: %s %s", msg.topic, msg.payload)
        entities = self._topic_entity_map.get(msg.topic)
        if entities:
            for entity in entities:
                entity.handle_mqtt_message(msg)
        else:
            # Optionally handle discovery here
            try:
                payload = msg.payload.decode()
                data = json.loads(payload)
                topic = msg.topic
                self.hass.loop.call_soon_threadsafe(
                    asyncio.create_task, self._handle_discovery_message(topic, data)
                )
            except Exception as err:
                _LOGGER.debug("Failed to process MQTT message: %s", err)

    async def _handle_discovery_message(self, topic: str, data: dict[str, Any]) -> None:
        """Handle a Home Assistant MQTT discovery message."""
        parts = topic.split("/")
        if len(parts) < 4:
            _LOGGER.debug("Invalid discovery topic: %s", topic)
            return
        component = parts[1]
        unique_id = data.get("unique_id") or parts[2]
        if component == "sensor":
            entity = MQTTDiscoveredSensor(data, unique_id)
            if self._sensor_add_entities:
                self._sensor_add_entities([entity])
            else:
                self._pending_sensors.append(entity)


class MQTTDiscoveredSensor(SensorEntity):
    """Representation of a discovered MQTT sensor."""

    def __init__(self, config: dict[str, Any], unique_id: str) -> None:
        """Initialize the sensor."""
        self._attr_name = config.get("name")
        self._state_topic = config.get("state_topic")
        self._value_template = config.get("value_template")
        self._attr_unique_id = unique_id
        self._attr_native_unit_of_measurement = config.get("unit_of_measurement")
        self._attr_icon = config.get("icon")
        self._attr_device_class = config.get("device_class")
        self._attr_state_class = config.get("state_class")
        self._attr_enabled_by_default = config.get("enabled_by_default", True)
        self._attr_suggested_display_precision = config.get(
            "suggested_display_precision"
        )
        self._state = None
        self._device_info_raw = config.get("device")

        _LOGGER.debug("MQTTDiscoveredSensor config: %s", config)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement for the entity."""
        return self._attr_native_unit_of_measurement

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for grouping entities."""
        if not self._device_info_raw:
            return None
        device = self._device_info_raw
        return DeviceInfo(
            identifiers={(device["identifiers"][0],)},
            manufacturer=device.get("manufacturer"),
            model=device.get("model"),
            name=device.get("name"),
            via_device=(device["via_device"],) if "via_device" in device else None,
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self._attr_unique_id

    @property
    def icon(self) -> str | None:
        """Return the icon for the entity."""
        return self._attr_icon

    @property
    def device_class(self) -> str | None:
        """Return the device class for the entity."""
        return self._attr_device_class

    @property
    def state_class(self) -> str | None:
        """Return the state class for the entity."""
        return self._attr_state_class

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topic when the entity is added to Home Assistant."""
        manager: VictronMqttManager = self.hass.data[DOMAIN]["manager"]
        _LOGGER.debug(
            "Registering entity for topic %s (id: %s)", self._state_topic, id(self)
        )
        manager._topic_entity_map[self._state_topic] = [self]
        manager._subscribed_topics.add(self._state_topic)
        manager.client.subscribe(self._state_topic)

    def handle_mqtt_message(self, msg) -> None:
        """Handle incoming MQTT message for this sensor."""
        payload = msg.payload.decode()
        _LOGGER.debug(
            "Received MQTT message for %s (id: %s): %s",
            self._attr_name,
            id(self),
            payload,
        )

        value = None

        # Try to parse as JSON if possible
        try:
            json_payload = json.loads(payload)
        except Exception:
            json_payload = None

        if self._value_template:
            template = Template(self._value_template, self.hass)
            try:
                value = template.async_render_with_possible_json_value(payload, None)
            except Exception as err:
                _LOGGER.debug(
                    "Failed to render value_template for %s: %s", self._attr_name, err
                )
                value = None
        elif json_payload is not None and "value" in json_payload:
            value = json_payload["value"]
        else:
            value = payload

        if value == "unknown":
            value = None

        # Try to cast to float if the unit is set (for measurements)
        if self._attr_native_unit_of_measurement and value is not None:
            try:
                value = float(value)
            except (ValueError, TypeError):
                value = None

        _LOGGER.debug(
            "Setting state for %s to %s (type: %s)", self._attr_name, value, type(value)
        )
        self._state = value
        self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        _LOGGER.debug(
            "native_value for %s is %s (type: %s, id: %s)",
            self._attr_name,
            self._state,
            type(self._state),
            id(self),
        )
        if self._attr_native_unit_of_measurement and self._state is not None:
            try:
                return float(self._state)
            except (ValueError, TypeError):
                return self._state
        return self._state


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Victron Energy from a config entry."""
    manager = VictronMqttManager(hass, entry)
    hass.data.setdefault(DOMAIN, {})["manager"] = manager
    manager.start()
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    manager: VictronMqttManager = hass.data[DOMAIN].pop("manager")
    if manager.client:
        manager.client.disconnect()
        manager.client.loop_stop()
    return True


# In sensor.py, you would call:
# hass.data[DOMAIN]["manager"].set_sensor_add_entities(async_add_entities)
