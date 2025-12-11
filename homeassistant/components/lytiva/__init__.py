"""Lytiva integration with independent MQTT connection (single platform - light only)."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

import paho.mqtt.client as mqtt_client

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


class LytivaMQTTHandler:
    """Handle MQTT connection and message routing for Lytiva integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        broker: str,
        port: int,
        username: str | None,
        password: str | None,
        discovery_prefix: str,
    ) -> None:
        """Initialize the MQTT handler."""
        self.hass = hass
        self.entry = entry
        self.broker = broker
        self.port = port
        self.discovery_prefix = discovery_prefix

        # Create MQTT client
        client_id = f"lytiva_{entry.entry_id}"
        self.client = mqtt_client.Client(
            client_id=client_id,
            callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2,
        )

        if username:
            self.client.username_pw_set(username, password)

        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message_fallback

        # Storage for entities and callbacks
        self.discovered_payloads: dict[str, dict[str, Any]] = {}
        self.entities_by_unique_id: dict[str, Any] = {}
        self.entities_by_address: dict[str, Any] = {}
        self.light_callbacks: list[Callable[[dict], None]] = []

    async def async_connect(self) -> bool:
        """Connect to MQTT broker."""
        try:
            await self.hass.async_add_executor_job(
                self.client.connect, self.broker, self.port, 60
            )
            await self.hass.async_add_executor_job(self.client.loop_start)
            return True
        except Exception as e:
            _LOGGER.error("Could not connect/start MQTT: %s", e)
            return False

    async def async_disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        try:
            self.client.publish("homeassistant/status", "offline", qos=1, retain=True)
        except Exception:
            pass

        try:
            await self.hass.async_add_executor_job(self.client.loop_stop)
        except Exception:
            pass

        try:
            await self.hass.async_add_executor_job(self.client.disconnect)
        except Exception:
            pass

    def register_light_callback(self, callback: Callable[[dict], None]) -> None:
        """Register a callback for light platform discovery."""
        self.light_callbacks.append(callback)

    def _on_connect(
        self, client: mqtt_client.Client, userdata: Any, flags: dict, reason_code: int, *args: Any
    ) -> None:
        """Handle MQTT connection."""
        if reason_code != 0:
            _LOGGER.error("MQTT connection failed: %s", reason_code)
            return

        _LOGGER.info("Connected to MQTT %s:%s", self.broker, self.port)

        try:
            client.publish("homeassistant/status", "online", qos=1, retain=True)
        except Exception:
            _LOGGER.exception("Failed to publish online status")

        # Subscribe to discovery and status topics
        self._subscribe_topics()

    def _subscribe_topics(self) -> None:
        """Subscribe to MQTT topics."""
        try:
            self.client.subscribe(f"{self.discovery_prefix}/+/+/config")
            self.client.message_callback_add(
                f"{self.discovery_prefix}/+/+/config", self._on_discovery
            )
        except Exception as e:
            _LOGGER.exception("Failed to subscribe discovery topic: %s", e)

        try:
            self.client.subscribe("LYT/+/NODE/E/STATUS")
            self.client.message_callback_add("LYT/+/NODE/E/STATUS", self._on_status)
            self.client.subscribe("LYT/+/GROUP/E/STATUS")
            self.client.message_callback_add("LYT/+/GROUP/E/STATUS", self._on_status)
        except Exception as e:
            _LOGGER.exception("Failed to subscribe STATUS topics: %s", e)

    def _on_message_fallback(
        self, client: mqtt_client.Client, userdata: Any, msg: mqtt_client.MQTTMessage
    ) -> None:
        """Fallback message handler."""
        _LOGGER.debug("Fallback on_message for topic %s", msg.topic)

    def _on_status(
        self, client: mqtt_client.Client, userdata: Any, message: mqtt_client.MQTTMessage
    ) -> None:
        """Handle status messages."""
        asyncio.run_coroutine_threadsafe(
            self._async_handle_status(message), self.hass.loop
        )

    async def _async_handle_status(self, message: mqtt_client.MQTTMessage) -> None:
        """Process status message asynchronously."""
        try:
            payload = json.loads(message.payload.decode("utf-8", errors="ignore"))
        except json.JSONDecodeError:
            _LOGGER.debug("Received non-JSON status payload on %s", message.topic)
            return
        except Exception as e:
            _LOGGER.exception("Error decoding status payload: %s", e)
            return

        # Find entity by address or unique_id
        entity = self._find_entity(payload)
        if entity and hasattr(entity, "_update_from_payload"):
            await entity._update_from_payload(payload)

    def _find_entity(self, payload: dict[str, Any]) -> Any | None:
        """Find entity by address or unique_id from payload."""
        address = payload.get("address")
        unique_id = payload.get("unique_id") or payload.get("uniqueId") or payload.get("uniqueid")

        # Try address lookup
        if address is not None:
            entity = self.entities_by_address.get(address) or self.entities_by_address.get(str(address))
            if entity:
                return entity

        # Try unique_id lookup
        if unique_id:
            entity = self.entities_by_unique_id.get(str(unique_id))
            if entity:
                return entity

        return None

    def _on_discovery(
        self, client: mqtt_client.Client, userdata: Any, message: mqtt_client.MQTTMessage
    ) -> None:
        """Handle discovery messages."""
        try:
            payload = json.loads(message.payload.decode("utf-8", errors="ignore"))
        except Exception:
            _LOGGER.exception("Invalid discovery JSON on %s", message.topic)
            return

        # Handle empty payload (device removal)
        if not payload:
            self._handle_device_removal(message.topic)
            return

        # Extract unique_id and platform
        unique_id = str(
            payload.get("unique_id")
            or payload.get("uniqueId")
            or payload.get("uniqueid")
            or payload.get("address")
        )
        if not unique_id:
            _LOGGER.debug("Discovery payload without unique id: %s", payload)
            return

        topic_parts = message.topic.split("/")
        platform = topic_parts[1] if len(topic_parts) >= 2 else None

        # Store discovery payload
        self.discovered_payloads[unique_id] = {
            "payload": payload,
            "platform": platform,
        }
        _LOGGER.debug(
            "Discovery payload stored for unique_id=%s platform=%s", unique_id, platform
        )

        # Notify platform callbacks
        if platform == "light":
            for callback in self.light_callbacks:
                self.hass.loop.call_soon_threadsafe(callback, payload)

    def _handle_device_removal(self, topic: str) -> None:
        """Handle device removal from empty discovery payload."""
        topic_parts = topic.split("/")
        if len(topic_parts) < 4:
            return

        platform = topic_parts[1]
        object_id = topic_parts[2]

        _LOGGER.warning(
            "Removing entity %s (platform %s) due to empty discovery payload",
            object_id,
            platform,
        )

        self.hass.loop.call_soon_threadsafe(
            self._remove_entity_and_device, object_id
        )

    def _remove_entity_and_device(self, object_id: str) -> None:
        """Remove entity and its device from registries."""
        entity_registry = async_get_entity_registry(self.hass)
        device_registry = async_get_device_registry(self.hass)

        # Find and remove entity
        entity_entry = None
        for entity_id, ent in list(entity_registry.entities.items()):
            if (
                ent.unique_id == object_id
                or ent.unique_id == str(object_id)
                or ent.unique_id.endswith(f"_{object_id}")
            ):
                entity_entry = ent
                entity_registry.async_remove(entity_id)
                break

        if not entity_entry:
            _LOGGER.error("Could not find entity with object_id %s", object_id)
            return

        # Remove device if no other entities
        if entity_entry.device_id:
            linked_entities = [
                e
                for e in entity_registry.entities.values()
                if e.device_id == entity_entry.device_id
            ]
            if not linked_entities:
                try:
                    device_registry.async_remove_device(entity_entry.device_id)
                except Exception as e:
                    _LOGGER.error("Failed to remove device: %s", e)

        # Clean up internal caches
        self.entities_by_unique_id.pop(object_id, None)
        self.entities_by_unique_id.pop(str(object_id), None)
        self.entities_by_address.pop(object_id, None)
        self.entities_by_address.pop(str(object_id), None)
        self.discovered_payloads.pop(object_id, None)
        self.discovered_payloads.pop(str(object_id), None)

    def dispatch_discovered_payloads(self) -> None:
        """Dispatch already discovered payloads to platform callbacks."""
        for item in list(self.discovered_payloads.values()):
            payload = item.get("payload")
            platform = item.get("platform")

            if platform == "light" and payload:
                for callback in self.light_callbacks:
                    self.hass.loop.call_soon_threadsafe(callback, payload)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lytiva integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Extract configuration
    broker = entry.data.get("broker")
    port = entry.data.get("port", 1883)
    username = entry.data.get("username")
    password = entry.data.get("password")
    discovery_prefix = (
        entry.options.get("discovery_prefix", "homeassistant")
        if entry.options
        else "homeassistant"
    )

    # Create MQTT handler
    mqtt_handler = LytivaMQTTHandler(
        hass, entry, broker, port, username, password, discovery_prefix
    )

    # Store handler and data
    hass.data[DOMAIN][entry.entry_id] = {
        "mqtt_handler": mqtt_handler,
        "mqtt_client": mqtt_handler.client,  # For backward compatibility
        "broker": broker,
        "port": port,
        "discovery_prefix": discovery_prefix,
        "discovered_payloads": mqtt_handler.discovered_payloads,
        "entities_by_unique_id": mqtt_handler.entities_by_unique_id,
        "entities_by_address": mqtt_handler.entities_by_address,
        "light_callbacks": mqtt_handler.light_callbacks,
        "register_light_callback": mqtt_handler.register_light_callback,
    }

    # Connect to MQTT
    if not await mqtt_handler.async_connect():
        return False

    # Set up platforms
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception as e:
        _LOGGER.exception("Error forwarding platforms: %s", e)
        return False

    # Dispatch any already-discovered payloads
    mqtt_handler.dispatch_discovered_payloads()

    _LOGGER.info("Lytiva integration setup complete for entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration and stop MQTT client."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        mqtt_handler = hass.data[DOMAIN][entry.entry_id].get("mqtt_handler")
        if mqtt_handler:
            await mqtt_handler.async_disconnect()

        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
