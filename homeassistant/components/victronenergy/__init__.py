"""Victron Energy integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
import ssl
from typing import Any

import paho.mqtt.client as mqtt_client
import paho.mqtt.properties as mqtt_properties
import paho.mqtt.subscribeoptions as mqtt_subscribeoptions
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .binary_sensor import MQTTDiscoveredBinarySensor
from .const import CONF_BROKER, CONF_PORT, CONF_USERNAME, DOMAIN
from .entity import VictronBaseEntity
from .mqtt_worker import MqttWorker
from .number import MQTTDiscoveredNumber
from .sensor import MQTTDiscoveredSensor
from .switch import MQTTDiscoveredSwitch
from .types import DeviceKey

_LOGGER = logging.getLogger(__name__)

# MQTT connection error mappings
_MQTT_ERROR_MESSAGES = {
    1: "Connection refused: Wrong protocol version.",
    2: "Connection refused: Bad client identifier.",
    3: "Connection refused: Server unavailable.",
    4: "Connection refused: Bad username or password.",
    5: "Connection refused: Not authorized. Check username/token configuration.",
}


# Platform configuration: entity factory and Platform enum for each supported platform
def _make_factory(
    entity_cls: type[VictronBaseEntity],
) -> Callable[
    [VictronMqttManager, DeviceKey, dict[str, Any], str, dict[str, Any]],
    VictronBaseEntity,
]:
    def factory(
        manager: VictronMqttManager,
        device_key: DeviceKey,
        device_info: dict[str, Any],
        unique_id: str,
        config: dict[str, Any],
    ) -> VictronBaseEntity:
        # Factory parameter order now matches entity constructor
        return entity_cls(manager, device_key, device_info, unique_id, config)

    return factory


_PLATFORM_CONFIG: dict[
    Platform,
    Callable[
        [VictronMqttManager, DeviceKey, dict[str, Any], str, dict[str, Any]],
        VictronBaseEntity,
    ],
] = {
    Platform.BINARY_SENSOR: _make_factory(MQTTDiscoveredBinarySensor),
    Platform.NUMBER: _make_factory(MQTTDiscoveredNumber),
    Platform.SENSOR: _make_factory(MQTTDiscoveredSensor),
    Platform.SWITCH: _make_factory(MQTTDiscoveredSwitch),
}

# Derived platforms list
_PLATFORMS: list[Platform] = list(_PLATFORM_CONFIG.keys())


def _extract_device_key_from_discovery(device_info: dict[str, Any]) -> DeviceKey | None:
    """Extract device key tuple from identifiers list."""
    identifiers = device_info.get("identifiers")
    if not identifiers or not isinstance(identifiers, list) or len(identifiers) == 0:
        return None

    # Use domain and first identifier as the device key
    return (DOMAIN, str(identifiers[0]))


def _extract_via_device_from_discovery(device_info: dict[str, Any]) -> DeviceKey | None:
    """Extract via_device as tuple from MQTT discovery message device info."""
    via_device = device_info.get("via_device")
    if not via_device:
        return None

    return (DOMAIN, str(via_device))


def _configure_tls(client: mqtt_client.Client) -> None:
    """Configure TLS settings for the MQTT client."""
    client.tls_set(
        ca_certs=None,
        certfile=None,
        keyfile=None,
        cert_reqs=ssl.CERT_NONE,
        tls_version=ssl.PROTOCOL_TLS,
        ciphers=None,
    )
    client.tls_insecure_set(True)  # Allow self-signed certificates


class VictronMqttManager:
    """Manages MQTT connection and dynamic entity creation."""

    hass: HomeAssistant
    entry: ConfigEntry
    client: mqtt_client.Client | None
    _platform_callbacks: dict[str, AddConfigEntryEntitiesCallback | None]
    _topic_entity_map: dict[str, set[VictronBaseEntity]]
    _entity_registry: dict[DeviceKey, dict[str, VictronBaseEntity]]
    _device_registry: set[DeviceKey]
    _topic_device_map: dict[str, DeviceKey]
    _topic_payload_cache: dict[str, bytes]
    _pending_via_device_discoveries: dict[DeviceKey, list[dict[str, Any]]]
    _mqtt_worker: MqttWorker | None
    _republish_timer_handle: asyncio.TimerHandle | None
    _republish_task: asyncio.Task | None
    _unique_id: str | None
    _keepalive_task: asyncio.Task | None
    _lock: asyncio.Lock

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the MQTT manager."""
        self.hass = hass
        self.entry = entry
        self.client = None
        self._platform_callbacks = dict.fromkeys(_PLATFORM_CONFIG)
        self._topic_entity_map = {}
        self._entity_registry = {}
        self._device_registry = set()
        self._topic_device_map = {}
        self._topic_payload_cache = {}
        self._pending_via_device_discoveries = {}
        self._mqtt_worker = None
        self._republish_timer_handle = None
        self._republish_task = None
        self._unique_id = None
        self._keepalive_task = None
        self._lock = asyncio.Lock()

    def _setup_and_run_client(self, broker: str, port: int) -> None:
        """Set up TLS (if needed) and run the MQTT client loop."""
        _LOGGER.debug("Setting up and connecting to MQTT broker at %s:%d", broker, port)
        if self.client is not None:
            # Configure TLS for secure MQTT (port 8883) in executor thread
            if port == 8883:
                _configure_tls(self.client)

            self.client.connect_async(broker, port, 60)
            _LOGGER.debug("Starting MQTT client background loop thread")
            # Start the paho background network loop in its own thread.
            # Using loop_start avoids blocking an executor thread with
            # loop_forever and lets us stop the loop with loop_stop during cleanup.
            try:
                self.client.loop_start()
            except (RuntimeError, OSError):
                _LOGGER.exception("Failed to start MQTT background loop thread")

    def _subscribe(
        self,
        topic: str
        | tuple[str, int]
        | tuple[str, mqtt_subscribeoptions.SubscribeOptions]
        | list[tuple[str, int]]
        | list[tuple[str, mqtt_subscribeoptions.SubscribeOptions]],
        qos: int = 0,
        options: mqtt_subscribeoptions.SubscribeOptions | None = None,
        properties: mqtt_properties.Properties | None = None,
    ) -> None:
        """Enqueue a subscribe to the MQTT broker (fire-and-forget)."""
        if self._mqtt_worker:
            self._mqtt_worker.enqueue("subscribe", topic, qos, options, properties)

    def _unsubscribe(
        self,
        topic: str | list[str],
        properties: mqtt_properties.Properties | None = None,
    ) -> None:
        """Enqueue an unsubscribe to the MQTT broker (fire-and-forget)."""
        if self._mqtt_worker:
            self._mqtt_worker.enqueue("unsubscribe", topic, properties)

    async def _keepalive_suppress_republish_task(self) -> None:
        """Publish keepalive JSON payload every 30 seconds."""
        topic = f"R/{self._unique_id}/keepalive"
        payload = json.dumps({"keepalive-options": ["suppress-republish"]})
        while True:
            self.publish(topic, payload)
            _LOGGER.debug(
                "Published periodic keepalive to topic: %s with payload: %s",
                topic,
                payload,
            )
            await asyncio.sleep(30)

    def _keepalive_task_done(self, task: asyncio.Task) -> None:
        """Mark that the keepalive task is not running."""
        self._keepalive_task = None

    def _send_republish(self) -> None:
        """Timer callback to send keepalive."""
        # Timer fired — clear the timer handle so queue logic is accurate
        self._republish_timer_handle = None

        if not self._unique_id:
            _LOGGER.warning("Cannot send keepalive - unique_id not available")
            return

        topic = f"R/{self._unique_id}/keepalive"
        payload = json.dumps({"keepalive-options": []})
        self.publish(topic, payload)

    def _queue_republish(self) -> None:
        """Queue a keepalive request using a resettable timer (batches multiple requests).

        This function should be called from the main event loop.

        """
        if self._republish_timer_handle:
            # Cancel existing timer if running
            self._republish_timer_handle.cancel()
            _LOGGER.debug("Reset keepalive timer (batching multiple requests)")
        else:
            _LOGGER.debug("Started keepalive timer for device batch")

        # Start/restart timer for 2 seconds from now
        self._republish_timer_handle = self.hass.loop.call_later(
            2.0, self._send_republish
        )

    def _store_device_info(
        self, device_key: DeviceKey, device_info: dict[str, Any]
    ) -> None:
        """Store device information for via_device dependency resolution."""
        if device_key:
            identifiers = device_info.get("identifiers")
            device_id = identifiers[0] if identifiers else "unknown"
            # Generate discovery topic from device identifier for mapping purposes
            topic = f"homeassistant/device/{device_id}/config"

            # Store the original device_info and maintain topic-to-device mapping
            self._device_registry.add(device_key)
            self._topic_device_map[topic] = device_key

            # Create entity registry entry for this device if it doesn't exist
            if device_key not in self._entity_registry:
                self._entity_registry[device_key] = {}

            _LOGGER.info("Stored device info - %s", device_info)
        else:
            _LOGGER.warning("Cannot store device info - %s", device_info)

    async def _ensure_device_registered(
        self, device_key: DeviceKey, device_info: dict[str, Any]
    ) -> None:
        """Register device in Home Assistant device registry once per discovery message."""
        if not device_info:
            return

        # Use the provided device_key for identifiers
        identifiers: set[DeviceKey] = {device_key}

        # Extract connections if available
        connections: set[tuple[str, str]] | None = device_info.get("connections")

        via_device = device_info.get("via_device")
        via_device_tuple: tuple[str, str] | None = None
        if via_device is not None:
            via_device_tuple = (DOMAIN, str(via_device))

        # Register/restore device in Home Assistant device registry
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers=identifiers,
            connections=connections,
            manufacturer=device_info.get("manufacturer"),
            name=device_info.get("name"),
            model=device_info.get("model"),
            sw_version=device_info.get("sw_version"),
            via_device=via_device_tuple,
        )

        _LOGGER.info(
            "Registered device in Home Assistant registry: %s (id: %s)",
            identifiers,
            device.id,
        )

    def _process_device_component(
        self,
        device_key: DeviceKey,
        device_entities: dict[str, VictronBaseEntity],
        unique_id: str,
        component_cfg: dict[str, Any],
        device_info: dict[str, Any],
    ) -> None:
        """Process a single device component - placeholder for future expansion."""
        # Attach device info to component config for update
        component_cfg = dict(component_cfg)  # shallow copy
        component_cfg["device"] = device_info
        platform = component_cfg.get("platform")
        component_cfg["platform"] = platform  # Ensure platform key exists
        is_empty_config = len(component_cfg) == 2  # only platform and device

        # Check if entity already exists first to avoid unnecessary processing
        existing_entity = device_entities.get(unique_id)
        if existing_entity:
            if is_empty_config:
                # Empty component config, only platform and device - mark existing entity as unavailable
                existing_entity.set_available(False)
                _LOGGER.info(
                    "Marked existing entity %s as unavailable due to empty config",
                    unique_id,
                )
                return

            # Entity exists, update its configuration with new discovery data
            existing_entity.update_config(component_cfg)
            _LOGGER.info("Updated existing entity %s with new configuration", unique_id)
            # Trigger state update to reflect any changes
            existing_entity.async_write_ha_state()
            return

        # Entity doesn't exist, validate platform and create entity directly
        if not platform or platform not in _PLATFORM_CONFIG:
            _LOGGER.warning(
                "Missing or unknown platform %s for entity %s, skipping",
                platform,
                unique_id,
            )
            return
        callback = self._platform_callbacks[platform]
        if not callback:
            _LOGGER.warning(
                "No callback registered for platform %s, cannot register entity %s",
                platform,
                unique_id,
            )
            return
        if is_empty_config:
            # Empty component config, only platform and device - skip creation
            _LOGGER.info(
                "Skipping creation of entity %s due to empty config", unique_id
            )
            return

        # Create entity
        _LOGGER.debug("Creating entity: unique_id=%s, platform=%s", unique_id, platform)
        # This invokes the registered factory callable to create the entity
        entity_factory = _PLATFORM_CONFIG[platform]
        entity = entity_factory(self, device_key, device_info, unique_id, component_cfg)
        if entity:
            # Store entity in nested registry structure
            if entity.unique_id:
                device_entities[entity.unique_id] = entity
            # This registers the entity with Home Assistant
            callback([entity])
        else:
            _LOGGER.warning(
                "Failed to create entity: unique_id=%s, platform=%s",
                unique_id,
                platform,
            )

    async def _process_device_components(
        self,
        device_info: dict[str, Any],
        components: dict[str, Any],
        device_key: DeviceKey,
    ) -> None:
        """Process device components - shared logic for discovery and pending via_device processing."""
        _LOGGER.info(
            "Processing discovery message with %d components for device %s",
            len(components),
            device_key,
        )

        device_entities = self._entity_registry[device_key]

        # Get current entities for this device to detect removals
        current_entity_ids = set(device_entities.keys())
        discovered_entity_ids = set(components.keys())

        # Mark entities as unavailable before processing new/updated entities
        entities_to_remove = current_entity_ids - discovered_entity_ids
        _LOGGER.info(
            "Marking as unavailable (no longer in discovery message) for device %s: %s",
            device_key,
            list(entities_to_remove),
        )
        for entity_id in entities_to_remove:
            entity = device_entities.get(entity_id)
            if entity:
                entity.set_available(False)

        # Process all components and create or update entities
        for unique_id, component_cfg in components.items():
            self._process_device_component(
                device_key, device_entities, unique_id, component_cfg, device_info
            )

    async def _process_device_after_via_check(
        self,
        device_key: DeviceKey,
        device_info: dict[str, Any],
        components: dict[str, Any],
    ) -> bool:
        """Process device after via_device availability check passes."""
        queue_republish = len(components) > 0
        self._store_device_info(device_key, device_info)
        await self._ensure_device_registered(device_key, device_info)
        await self._process_device_components(device_info, components, device_key)

        # Check if any pending via_device discoveries can now be processed for this specific device
        pending_for_device = self._pending_via_device_discoveries.get(device_key, [])

        for discovery_data in pending_for_device:
            pending_device_info = discovery_data["device"]
            pending_components = discovery_data["components"]

            # Extract device key for this specific deferred device
            pending_device_key = _extract_device_key_from_discovery(pending_device_info)
            if not pending_device_key:
                _LOGGER.warning(
                    "Invalid pending discovery: device has no valid identifiers"
                )
                continue

            _LOGGER.info(
                "Processing deferred discovery with %d components: via_device '%s' is now available",
                len(pending_components),
                device_key,
            )

            # Process deferred device and accumulate new entities count
            queue_republish = (
                queue_republish
                | await self._process_device_after_via_check(
                    pending_device_key, pending_device_info, pending_components
                )
            )

        # Clean up processed pending discoveries
        self._pending_via_device_discoveries.pop(device_key, None)
        _LOGGER.info("Processed pending discoveries for via_device %s", device_key)

        return queue_republish

    async def _handle_discovery_message(self, topic: str, payload: bytes) -> None:
        """Handle a Home Assistant MQTT discovery message."""
        async with self._lock:
            # Check payload cache to avoid reprocessing identical discovery messages
            cached_payload = self._topic_payload_cache.get(topic)
            if cached_payload is not None and cached_payload == payload:
                _LOGGER.debug(
                    "Ignoring duplicate discovery payload for topic: %s", topic
                )
                return

            # Update cache with new payload
            self._topic_payload_cache[topic] = payload
            _LOGGER.debug(
                "Cached new discovery payload for topic: %s (size: %d bytes)",
                topic,
                len(payload),
            )

            # Check for empty payload - this indicates device should be removed
            if len(payload) == 0:
                _LOGGER.debug("Received empty discovery config on topic: %s", topic)
                # Look up which device this topic belongs to and remove it
                device_key = self._topic_device_map.get(topic)
                if device_key and device_key in self._device_registry:
                    # Mark all entities for this device as unavailable before removing
                    for entity in self._entity_registry.get(device_key, {}).values():
                        entity.set_available(False)

                    # Remove device from our administration
                    self._device_registry.remove(device_key)
                    del self._topic_device_map[topic]
                    _LOGGER.debug("Removed device %s from registry", device_key)
                else:
                    _LOGGER.debug("Empty config received for unknown topic: %s", topic)
                return

            # Decode and parse JSON payload
            try:
                payload_str = payload.decode()
                data = json.loads(payload_str)
                _LOGGER.debug("Received config on topic %s: %s", topic, data)
            except json.JSONDecodeError as err:
                _LOGGER.warning("Failed to process device discovery JSON: %s", err)
                return
            except UnicodeDecodeError as err:
                _LOGGER.warning("Failed to decode discovery message bytes: %s", err)
                return

            components = data.get("components")
            device_info = data.get("device")
            if not components or not device_info:
                _LOGGER.debug("Invalid discovery message: missing components or device")
                return

            # Check if device has valid identifiers
            device_key = _extract_device_key_from_discovery(device_info)
            if not device_key:
                _LOGGER.debug(
                    "Invalid discovery message: device has no valid identifiers"
                )
                return

            # Check via_device availability once for the entire device (not per component)
            via_device = _extract_via_device_from_discovery(device_info)

            # Handle discovery deferral based on via_device availability before processing components
            if via_device and via_device not in self._device_registry:
                # Via_device doesn't exist yet, defer entire discovery data processing
                if via_device not in self._pending_via_device_discoveries:
                    self._pending_via_device_discoveries[via_device] = []
                self._pending_via_device_discoveries[via_device].append(data)
                _LOGGER.info(
                    "Deferring discovery data of %s until via_device %s is available",
                    device_key,
                    via_device,
                )
                return  # Exit early, don't process any components

            # Process device after via_device check passes (store info, register, process components)
            queue_republish = await self._process_device_after_via_check(
                device_key, device_info, components
            )

            if queue_republish:
                self._queue_republish()

    def _handle_state_message(self, topic: str, payload: bytes) -> None:
        """Handle state messages by passing them on to the entities."""
        entities: set[VictronBaseEntity] = self._topic_entity_map.get(topic, set())
        for entity in entities:
            entity.handle_mqtt_message(topic, payload)

    async def _handle_connect(self) -> None:
        """Handle MQTT connection."""
        async with self._lock:
            if not self.client:
                return

            # CLear the discovery data cache so that all discovery messages are reprocessed
            self._topic_payload_cache.clear()
            _LOGGER.info("Cleared discovery payload cache on MQTT reconnect")

            # Subscribe to all discovery topics
            # When these are received, the entities will be created/updated accordingly
            # which will also re-subscribe to their state topics
            self._subscribe("homeassistant/#")
            _LOGGER.info("Subscribed to homeassistant/# discovery topics")

            # Start task to periodically send a keepalive with suppress-republish option.
            # This keepalive is just to tell the GX MQTT broker that someone is still listening.
            if self._unique_id and not self._keepalive_task:
                # Start keepalive as a background task tied to the config entry.
                # It needs to be a background tasks because during startup, Home Assistant
                # waits until all created regular tasks are done.
                try:
                    self._keepalive_task = self.entry.async_create_background_task(
                        self.hass,
                        self._keepalive_suppress_republish_task(),
                        "victron keepalive",
                    )
                    self._keepalive_task.add_done_callback(self._keepalive_task_done)
                    _LOGGER.debug(
                        "Started keepalive task for unique ID: %s", self._unique_id
                    )
                except Exception:
                    _LOGGER.exception("Failed starting keepalive background task")
            else:
                _LOGGER.debug(
                    "Keepalive task already started for unique ID: %s", self._unique_id
                )

    async def _handle_disconnect(self) -> None:
        """Handle MQTT disconnection."""
        async with self._lock:
            if not self.client:
                # Busy with the cleanup
                return

            _LOGGER.info(
                "MQTT disconnection - marking all entities as unavailable and devices as removed"
            )
            # Mark all entities as unavailable
            for entity_dict in self._entity_registry.values():
                for entity in entity_dict.values():
                    entity.set_available(False)

            # Clear the device registry to force re-registration on reconnect
            self._device_registry.clear()
            self._topic_device_map.clear()

    def _on_connect(self, client, userdata, flags, rc) -> None:
        """Handle MQTT connection."""
        _LOGGER.info("MQTT connection callback - result code: %s", rc)
        if rc != 0:
            error_msg = _MQTT_ERROR_MESSAGES.get(rc, f"Unknown error (code {rc})")
            _LOGGER.error(
                "Failed to connect to MQTT broker - result code %s: %s. %s",
                rc,
                mqtt_client.connack_string(rc),
                error_msg,
            )
            return

        _LOGGER.info(
            "Successfully connected to MQTT broker at %s:%d",
            self.entry.data[CONF_BROKER],
            self.entry.data[CONF_PORT],
        )

        try:
            # schedule the in-loop handler
            asyncio.run_coroutine_threadsafe(self._handle_connect(), self.hass.loop)
        except Exception:
            _LOGGER.exception("Failed scheduling connect handler")

    def _on_message(self, client, userdata, msg) -> None:
        """Handle all MQTT messages."""
        _LOGGER.debug("_on_message: %s %s", msg.topic, msg.payload)
        topic = msg.topic
        payload = msg.payload
        if topic.startswith("homeassistant/device/"):
            try:
                asyncio.run_coroutine_threadsafe(
                    self._handle_discovery_message(topic, payload), self.hass.loop
                )
            except Exception:
                _LOGGER.exception(
                    "Failed scheduling discovery message handler for topic %s",
                    topic,
                )
        else:
            self.hass.loop.call_soon_threadsafe(
                self._handle_state_message, topic, payload
            )

    def _on_disconnect(self, client, userdata, rc) -> None:
        """Handle MQTT disconnection."""
        _LOGGER.info("Disconnected from MQTT broker with result code: %s", rc)
        if rc != 0:
            _LOGGER.warning(
                "Unexpected disconnection from MQTT broker with result code %s", rc
            )
        try:
            # schedule the in-loop handler
            asyncio.run_coroutine_threadsafe(self._handle_disconnect(), self.hass.loop)
        except Exception:
            _LOGGER.exception("Failed scheduling disconnect handler")

    def start(self) -> None:
        """Start the MQTT client in a background thread and prepare keepalive publishing."""
        broker = self.entry.data[CONF_BROKER]
        port = self.entry.data[CONF_PORT]
        username = self.entry.data.get(CONF_USERNAME)
        token = self.entry.data.get("token")  # Use token instead of password
        unique_id = self.entry.unique_id

        _LOGGER.debug(
            "Starting MQTT connection to %s:%s with Unique ID %s",
            broker,
            port,
            unique_id,
        )

        client = mqtt_client.Client()

        # Set up authentication
        if username and token:
            client.username_pw_set(username, token)
            _LOGGER.debug("MQTT authentication configured with token")
        else:
            _LOGGER.debug("No authentication configured (anonymous MQTT)")

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect

        self.client = client
        self._unique_id = unique_id

        # Start background MQTT worker for blocking client calls
        try:
            self._mqtt_worker = MqttWorker(self.client)
            self._mqtt_worker.start()
        except Exception:
            _LOGGER.exception("Failed to start MQTT worker thread")

        self.hass.async_add_executor_job(self._setup_and_run_client, broker, port)

    async def restore_devices_from_registry(self) -> None:
        """Restore devices from Home Assistant's device registry on startup."""
        _LOGGER.info("Restoring devices from Home Assistant device registry")

    async def cleanup(self) -> None:
        """Clean up resources when the manager is being destroyed."""
        _LOGGER.info("Cleaning up VictronMqttManager resources")

        # Cancel any running keepalive timer
        if self._republish_timer_handle:
            _LOGGER.debug("Cancelling keepalive timer")
            self._republish_timer_handle.cancel()
            self._republish_timer_handle = None

        # Cancel republish task if running and await its completion
        if self._republish_task:
            _LOGGER.debug("Cancelling republish task")
            try:
                self._republish_task.cancel()
                try:
                    await asyncio.wait_for(self._republish_task, timeout=10.0)
                except asyncio.CancelledError:
                    _LOGGER.debug("Republish task cancelled")
                except TimeoutError:
                    _LOGGER.warning("Timed out waiting for republish task to finish")
                except Exception:
                    _LOGGER.exception(
                        "Error while waiting for republish task to finish"
                    )
            except Exception:
                _LOGGER.exception("Error cancelling republish task")
            finally:
                self._republish_task = None

        # Cancel keepalive task if running and await its completion
        if self._keepalive_task:
            _LOGGER.debug("Cancelling keepalive background task")
            try:
                self._keepalive_task.cancel()
                try:
                    await asyncio.wait_for(self._keepalive_task, timeout=10.0)
                except asyncio.CancelledError:
                    _LOGGER.debug("Keepalive task cancelled")
                except TimeoutError:
                    _LOGGER.warning("Timed out waiting for keepalive task to finish")
                except Exception:
                    _LOGGER.exception(
                        "Error while waiting for keepalive task to finish"
                    )
            except Exception:
                _LOGGER.exception("Error cancelling keepalive task")
            finally:
                self._keepalive_task = None

        # Clear all registries
        # Clear all internal registries
        self._entity_registry.clear()
        self._device_registry.clear()
        self._topic_device_map.clear()
        self._topic_payload_cache.clear()
        self._pending_via_device_discoveries.clear()
        self._topic_entity_map.clear()

        # Disconnect MQTT if still connected
        # Stop the mqtt worker before disconnecting the client
        if self._mqtt_worker:
            try:
                self._mqtt_worker.stop()
            except Exception:
                _LOGGER.exception("Error stopping MQTT worker")
            finally:
                self._mqtt_worker = None

        if self.client:
            try:
                # Unsubscribe from all topics to clean up server-side subscriptions
                await self.hass.async_add_executor_job(self.client.unsubscribe, "#")
                _LOGGER.debug("Unsubscribed from all topics")
            except (RuntimeError, OSError, AttributeError):
                _LOGGER.debug(
                    "Error unsubscribing from topics (client may already be disconnected)"
                )

            try:
                # Stop the network loop first
                await self.hass.async_add_executor_job(self.client.loop_stop)
                _LOGGER.debug("MQTT loop stopped")
            except Exception:
                _LOGGER.exception("Error stopping MQTT loop")

            try:
                # Disconnect the client
                await self.hass.async_add_executor_job(self.client.disconnect)
                _LOGGER.debug("MQTT client disconnected")
            except Exception:
                _LOGGER.exception("Error disconnecting MQTT client")

            # Clear event handlers to remove callback references
            try:
                self.client.on_connect = None
                self.client.on_message = None
                self.client.on_disconnect = None
                _LOGGER.debug("Cleared MQTT event handlers")
            except (RuntimeError, OSError, AttributeError):
                _LOGGER.debug("Error clearing MQTT event handlers")

            # Clear client reference
            self.client = None
        _LOGGER.info("VictronMqttManager cleanup completed")

    def set_platform_add_entities(
        self, platform: str, add_entities: AddConfigEntryEntitiesCallback
    ) -> None:
        """Set the callback to add entities for a specific platform."""
        if platform not in self._platform_callbacks:
            _LOGGER.warning("Unknown platform: %s", platform)
            return

        self._platform_callbacks[platform] = add_entities

    def subscribe_entity(self, entity: VictronBaseEntity) -> None:
        """Subscribe an entity to its state topic."""
        if entity.state_topic is None:
            return

        if entity.state_topic not in self._topic_entity_map:
            self._topic_entity_map[entity.state_topic] = set()
            self._subscribe(entity.state_topic)

        self._topic_entity_map[entity.state_topic].add(entity)

    def unsubscribe_entity(self, entity: VictronBaseEntity) -> None:
        """Unsubscribe an entity from its state topic."""
        if entity.state_topic is None:
            return
        if entity.state_topic not in self._topic_entity_map:
            return

        entity_set = self._topic_entity_map[entity.state_topic]
        if entity not in entity_set:
            return

        entity_set.remove(entity)
        if not entity_set:
            # No more entities for this topic, unsubscribe
            del self._topic_entity_map[entity.state_topic]
            self._unsubscribe(entity.state_topic)

    def register_entity(self, entity: VictronBaseEntity) -> None:
        """Register an entity with the manager."""
        self.subscribe_entity(entity)

    def unregister_entity(self, entity: VictronBaseEntity) -> None:
        """Unregister an entity from the manager."""
        self.unsubscribe_entity(entity)

        if not entity.unique_id:
            return
        # Remove entity from device-specific registry
        device_key = entity.device_key
        if device_key not in self._entity_registry:
            return
        device_entities = self._entity_registry[device_key]
        del device_entities[entity.unique_id]
        _LOGGER.debug(
            "Unregistered entity %s from device %s", entity.entity_id, device_key
        )

    def publish(
        self,
        topic: str,
        payload: str | bytes | bytearray | float | None = None,
        qos: int = 0,
        retain: bool = False,
        props: mqtt_properties.Properties | None = None,
    ) -> None:
        """Publish a message to the MQTT broker using the executor to avoid blocking."""
        if self._mqtt_worker:
            self._mqtt_worker.enqueue("publish", topic, payload, qos, retain, props)

    def has_device_key(self, device_key: DeviceKey) -> bool:
        """Return True if the device_key is in the device registry."""
        return device_key in self._device_registry


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Victron Energy from a config entry."""
    try:
        manager = VictronMqttManager(hass, entry)
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
        entry.runtime_data = manager
        manager.start()

        # Register a service to allow publishing arbitrary MQTT messages to
        # the broker associated with a config entry. Register once for the
        # domain and keep a marker in hass.data so we unregister when the
        # last entry is removed.
        domain_store = hass.data.setdefault(DOMAIN, {})
        if not domain_store.get("_service_registered"):

            def _resolve_entry_id_from_device(device_id: str) -> str | None:
                device_registry = dr.async_get(hass)
                device = device_registry.async_get(device_id)
                if not device:
                    return None
                # Return the first config entry id attached to the device
                for cfg in device.config_entries:
                    return cfg
                return None

            def _handle_publish(call: ServiceCall) -> None:
                data = call.data
                entry_id = data["config_entry"]
                topic = data["topic"]
                payload = data["payload"]
                qos = int(data.get("qos", 0))
                retain = bool(data.get("retain", False))

                # Ensure the config entry exists and is set up (has a manager)
                entry_obj = hass.config_entries.async_get_entry(entry_id)
                if entry_obj is None:
                    raise HomeAssistantError(f"Config entry {entry_id} does not exist")

                mgr: VictronMqttManager | None = hass.data.get(DOMAIN, {}).get(entry_id)
                if not mgr:
                    raise HomeAssistantError(
                        f"Config entry {entry_id} exists but is not loaded/instantiated (cannot publish)"
                    )

                # Ensure topic is a string
                if not isinstance(topic, str):
                    _LOGGER.error("Invalid topic type: %s", type(topic))
                    return

                # Resolve unique_id for this entry (prefer manager.entry.unique_id)
                unique_id = mgr.entry.unique_id
                if not unique_id:
                    _LOGGER.error("No unique_id for entry_id %s", entry_id)
                    return

                stripped = topic.lstrip("/")
                topic = f"W/{unique_id}/{stripped}"

                try:
                    # If payload is a non-string (dict/list), encode to JSON string
                    if not isinstance(payload, (str, bytes, bytearray)):
                        payload_to_send: str | bytes | bytearray = json.dumps(payload)
                    else:
                        payload_to_send = payload
                    mgr.publish(topic, payload_to_send, qos, retain)
                except Exception:
                    _LOGGER.exception("Failed publishing MQTT message to %s", topic)

            publish_schema = vol.Schema(
                {
                    vol.Required("config_entry"): str,
                    vol.Required("topic"): str,
                    vol.Required("payload"): object,
                    vol.Optional("qos", default=0): vol.All(
                        int, vol.Range(min=0, max=2)
                    ),
                    vol.Optional("retain", default=False): bool,
                }
            )

            hass.services.async_register(
                DOMAIN, "publish", _handle_publish, schema=publish_schema
            )

            domain_store["_service_registered"] = True
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
        # Restore devices from HA device registry now that the platforms are set up
        await manager.restore_devices_from_registry()

    except OSError as err:
        _LOGGER.debug("MQTT connection failed: %s", err)
        raise ConfigEntryNotReady from err
    except (ValueError, RuntimeError, TypeError) as err:
        _LOGGER.debug("Unexpected setup error", exc_info=True)
        raise ConfigEntryError from err
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Starting unload process for Victron Energy entry %s", entry.entry_id)

    # Get the manager before removing it from hass.data
    manager: VictronMqttManager | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    # First unload platforms that were forwarded during setup
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    _LOGGER.debug("Platforms unloaded: %s", unload_ok)

    # Remove the manager from hass.data
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    # Clean up manager resources regardless of platform unload result
    if manager:
        await manager.cleanup()
        _LOGGER.debug("Manager cleanup completed")
    else:
        _LOGGER.warning("No manager found for entry %s during unload", entry.entry_id)

    # Clean up the domain data if no more entries exist
    if DOMAIN in hass.data and not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN, None)
        _LOGGER.debug("Removed empty domain data")

    # If there are no more entries left for this domain, remove the domain-level service
    domain_store = hass.data.get(DOMAIN, {})
    if not domain_store:
        try:
            hass.services.async_remove(DOMAIN, "publish")
        except Exception:
            _LOGGER.exception("Failed removing victronenergy.publish service")

    _LOGGER.info(
        "Victron Energy integration unloaded for entry %s (platforms unloaded=%s)",
        entry.entry_id,
        unload_ok,
    )
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Return whether a user is allowed to remove this device."""

    # Get the manager to check if this device is active
    manager: VictronMqttManager = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    if not manager:
        # Manager not available, allow removal
        _LOGGER.info("Manager not available, allowing device removal")
        return True

    # Check if the manager has any identifier as device_key
    # If any identifier is still present in the manager, we should NOT remove the
    # device from the registry. Only allow removal when none of the identifiers
    # are known to the manager.
    has_active_identifier = any(
        manager.has_device_key(identifier) for identifier in device_entry.identifiers
    )
    can_remove = not has_active_identifier
    _LOGGER.info(
        "Checking if device (%s) can be removed -> has_active_identifier=%s, can_remove=%s",
        device_entry.identifiers,
        has_active_identifier,
        can_remove,
    )
    return can_remove
