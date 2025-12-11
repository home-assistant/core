"""Victron Energy integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
import json
import logging
import ssl
from typing import Any

import paho.mqtt.client as mqtt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .binary_sensor import MQTTDiscoveredBinarySensor
from .const import CONF_BROKER, CONF_PORT, CONF_USERNAME, DOMAIN
from .number import MQTTDiscoveredNumber
from .sensor import MQTTDiscoveredSensor
from .switch import MQTTDiscoveredSwitch

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
_PLATFORM_CONFIG = {
    "sensor": {
        "factory": lambda config, unique_id, manager: MQTTDiscoveredSensor(
            config, unique_id, manager
        ),
        "platform": Platform.SENSOR,
    },
    "binary_sensor": {
        "factory": lambda config, unique_id, manager: MQTTDiscoveredBinarySensor(
            config, unique_id, manager
        ),
        "platform": Platform.BINARY_SENSOR,
    },
    "switch": {
        "factory": lambda config, unique_id, manager: MQTTDiscoveredSwitch(
            config, unique_id, manager
        ),
        "platform": Platform.SWITCH,
    },
    "number": {
        "factory": lambda config, unique_id, manager: MQTTDiscoveredNumber(
            config, unique_id, manager
        ),
        "platform": Platform.NUMBER,
    },
}

# Derived platforms list
_PLATFORMS: list[Platform] = [
    config["platform"] for config in _PLATFORM_CONFIG.values()
]


def _extract_device_key_from_identifiers(identifiers) -> tuple[str, str] | None:
    """Extract device key tuple from identifiers list."""
    if not identifiers or not isinstance(identifiers, list) or len(identifiers) == 0:
        return None

    # Use domain and first identifier as the device key
    return (DOMAIN, str(identifiers[0]))


def _extract_via_device_from_discovery(
    device_info: dict[str, Any],
) -> tuple[str, str] | None:
    """Extract via_device as tuple from MQTT discovery message device info."""
    via_device = device_info.get("via_device")
    if not via_device:
        return None

    return (DOMAIN, str(via_device))


class VictronMqttManager:
    """Manages MQTT connection and dynamic entity creation."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the MQTT manager."""
        self.hass = hass
        self.entry = entry
        self.client: mqtt.Client | None = None
        # Platform entity management
        self._platform_callbacks: dict[
            str, Callable[[Sequence[Entity]], None] | None
        ] = {platform: None for platform in _PLATFORM_CONFIG}
        self._pending_entities: dict[str, list[Entity]] = {
            platform: [] for platform in _PLATFORM_CONFIG
        }
        self._connected = asyncio.Event()
        self._subscribed_topics: set[str] = set()
        self._topic_entity_map: dict[str, list[Entity]] = {}
        self._entity_registry: dict[str, Entity] = {}  # Track entities by unique_id
        self._device_registry: dict[
            tuple[str, str], dict[str, Any]
        ] = {}  # Track device info by identifiers
        self._pending_via_device_entities: list[
            tuple[dict[str, Any], str, str]
        ] = []  # Entity configs waiting for via_device
        self._via_device_lock = (
            asyncio.Lock()
        )  # Synchronize via_device dependency operations
        self._keepalive_timer_handle: asyncio.TimerHandle | None = (
            None  # Resettable keepalive timer
        )
        self._retry_pending_task: asyncio.Task | None = (
            None  # Task for retrying pending entities
        )
        self._unique_id: str | None = None
        self._keepalive_task_started = False
        self._platforms_setup_complete = False

    def set_platform_add_entities(
        self, platform: str, add_entities: Callable[[Sequence[Entity]], None]
    ) -> None:
        """Set the callback to add entities for a specific platform."""
        if platform not in self._platform_callbacks:
            _LOGGER.warning("Unknown platform: %s", platform)
            return

        self._platform_callbacks[platform] = add_entities

    # Legacy methods for backward compatibility
    def set_sensor_add_entities(
        self, add_entities: Callable[[Sequence[Entity]], None]
    ) -> None:
        self.set_platform_add_entities("sensor", add_entities)

    def set_binary_sensor_add_entities(
        self, add_entities: Callable[[Sequence[Entity]], None]
    ) -> None:
        self.set_platform_add_entities("binary_sensor", add_entities)

    def set_switch_add_entities(
        self, add_entities: Callable[[Sequence[Entity]], None]
    ) -> None:
        self.set_platform_add_entities("switch", add_entities)

    def set_number_add_entities(
        self, add_entities: Callable[[Sequence[Entity]], None]
    ) -> None:
        self.set_platform_add_entities("number", add_entities)

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

        client.on_connect = self._on_connect
        client.on_message = self._on_message

        self.client = client
        self._unique_id = unique_id

        # Run the MQTT client setup and connection in background thread
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self._setup_and_run_client, broker, port)

    def _configure_tls(self, client: mqtt.Client) -> None:
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
        _LOGGER.info("TLS configured for secure MQTT")

    def _setup_and_run_client(self, broker: str, port: int) -> None:
        """Set up TLS (if needed) and run the MQTT client loop."""
        _LOGGER.debug("Setting up and connecting to MQTT broker at %s:%d", broker, port)
        if self.client is not None:
            # Configure TLS for secure MQTT (port 8883) in executor thread
            if port == 8883:
                self._configure_tls(self.client)

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
            _LOGGER.info(
                "Subscribed to homeassistant/# discovery topics, result: %s", result
            )

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
            error_msg = _MQTT_ERROR_MESSAGES.get(rc, f"Unknown error (code {rc})")
            _LOGGER.error(
                "Failed to connect to MQTT broker - result code %s: %s. %s",
                rc,
                mqtt.connack_string(rc),
                error_msg,
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
        # New format: data contains "components" (dict of sensors/switches/numbers) and "device"
        components = data.get("components")
        device_info = data.get("device")
        if not components or not device_info:
            _LOGGER.debug("Invalid discovery message: missing components or device")
            return

        async with self._via_device_lock:
            new_entities_by_platform = {platform: [] for platform in _PLATFORM_CONFIG}
            updated_entities = []

        # Store device info for via_device dependency resolution
        self._store_device_info(device_info)

        # Check via_device availability once for the entire device (not per component)
        via_device_raw = device_info.get("via_device")
        via_device = (
            _extract_via_device_from_discovery(device_info) if via_device_raw else None
        )
        via_device_available = not via_device or self._is_via_device_available(
            via_device
        )

        _LOGGER.info(
            "Processing discovery message with %d components for device: %s (via_device: %s, available: %s)",
            len(components),
            device_info.get("identifiers"),
            via_device,
            via_device_available,
        )

        # Process all components to prepare entity configurations for creation
        new_entity_configs = []  # List of (component_cfg, unique_id, platform) tuples for new entities

        for unique_id, component_cfg in components.items():
            # Validate component has unique_id attribute and it's not empty
            component_unique_id = component_cfg.get("unique_id")
            if not component_unique_id or not str(component_unique_id).strip():
                _LOGGER.info(
                    "Component missing or has empty unique_id attribute, skipping: %s",
                    component_cfg,
                )
                continue

            # Attach device info to each component config
            component_cfg = dict(component_cfg)  # shallow copy
            component_cfg["device"] = device_info
            platform = component_cfg.get("platform")

            # Validate platform is present and supported
            if not platform:
                _LOGGER.warning("Missing platform for entity %s, skipping", unique_id)
                continue

            if platform not in _PLATFORM_CONFIG:
                _LOGGER.warning(
                    "Unsupported platform '%s' for entity %s, skipping",
                    platform,
                    unique_id,
                )
                continue

            # Check if entity already exists
            existing_entity = self._entity_registry.get(unique_id)
            if existing_entity:
                # Update existing entity configuration
                existing_entity.update_config(component_cfg)
                updated_entities.append(existing_entity)
                _LOGGER.debug(
                    "Updated existing entity %s with new configuration", unique_id
                )
                # Trigger state update to reflect any changes
                existing_entity.async_write_ha_state()
            else:
                # Store config for potential entity creation (deferred until via_device is available)
                new_entity_configs.append((component_cfg, unique_id, platform))

        # Handle new entity configurations based on via_device availability
        if not via_device_available:
            # All entities depend on via_device that doesn't exist yet, defer entity creation entirely
            for component_cfg, unique_id, platform in new_entity_configs:
                self._pending_via_device_entities.append(
                    (component_cfg, unique_id, platform)
                )
            _LOGGER.info(
                "DEFERRING %d entity configs: waiting for via_device '%s' to become available. Current pending count: %d",
                len(new_entity_configs),
                via_device,
                len(self._pending_via_device_entities),
            )
        else:
            # Via_device is available or not needed, create entities and add to platforms immediately
            new_entities = []
            for component_cfg, unique_id, platform in new_entity_configs:
                entity_factory = _PLATFORM_CONFIG[platform]["factory"]
                entity = entity_factory(component_cfg, unique_id, self)
                if entity:
                    new_entities.append((entity, platform))
                    if platform in new_entities_by_platform:
                        new_entities_by_platform[platform].append(entity)
                    self._entity_registry[entity.unique_id] = entity

            if new_entities:
                if via_device:
                    _LOGGER.info(
                        "CREATED and ADDING %d entities to platforms: via_device '%s' is available",
                        len(new_entities),
                        via_device,
                    )
                else:
                    _LOGGER.info(
                        "CREATED and ADDING %d entities to platforms: no via_device dependency",
                        len(new_entities),
                    )

            if updated_entities:
                _LOGGER.info(
                    "Updated configuration for %d existing entities",
                    len(updated_entities),
                )

            # Check if any pending via_device entities can now be added to platforms
            await self._process_pending_via_device_entities(new_entities_by_platform)

            # Schedule a retry for remaining pending entities in case of timing issues
            if self._pending_via_device_entities and not self._retry_pending_task:
                self._retry_pending_task = asyncio.create_task(
                    self._retry_pending_entities()
                )

        # Add entities to platforms outside the lock to prevent deadlock
        self._add_entities_to_platforms(new_entities_by_platform)

        # If we created new entities, queue a keepalive to get current values
        if any(entities for entities in new_entities_by_platform.values()):
            self._queue_keepalive_for_device(device_info.get("identifiers"))

    def _store_device_info(self, device_info: dict[str, Any]) -> None:
        """Store device information for via_device dependency resolution."""
        identifiers = device_info.get("identifiers")
        device_key = _extract_device_key_from_identifiers(identifiers)

        if device_key:
            self._device_registry[device_key] = device_info
            _LOGGER.info(
                "STORED device info: identifiers=%s -> device_key=%s, via_device=%s. Total devices stored: %d",
                identifiers,
                device_key,
                device_info.get("via_device"),
                len(self._device_registry),
            )
        else:
            _LOGGER.warning(
                "Cannot store device info - invalid identifiers: %s (type: %s)",
                identifiers,
                type(identifiers),
            )

    def _is_via_device_available(self, via_device: tuple[str, str]) -> bool:
        """Check if a via_device is available in our stored device registry."""
        _LOGGER.info(
            "Checking via_device '%s' (type: %s) availability. Local registry: %s",
            via_device,
            type(via_device),
            list(self._device_registry.keys()),
        )

        # Check if device exists in our local registry
        if via_device in self._device_registry:
            _LOGGER.info("✅ Via device '%s' found in local registry", via_device)
            return True

        _LOGGER.debug(
            "❌ Via device '%s' NOT found. Checked local registry (%d devices)",
            via_device,
            len(self._device_registry),
        )

        return False

    def _queue_keepalive_for_device(self, device_identifiers) -> None:
        """Queue a keepalive request using a resettable timer (batches multiple requests)."""
        if not device_identifiers or not self._unique_id:
            return

        # Cancel existing timer if running
        if self._keepalive_timer_handle:
            self._keepalive_timer_handle.cancel()
            _LOGGER.debug("Reset keepalive timer (batching multiple requests)")
        else:
            _LOGGER.debug("Started keepalive timer for device batch")

        # Start/restart timer for 2 seconds from now
        loop = asyncio.get_running_loop()
        self._keepalive_timer_handle = loop.call_later(2.0, self._send_keepalive_now)

    def _send_keepalive_now(self) -> None:
        """Timer callback to send keepalive."""
        try:
            # Send the keepalive
            if self.client and self._unique_id:
                topic = f"R/{self._unique_id}/keepalive"
                payload = json.dumps({"keepalive-options": []})
                self.client.publish(topic, payload=payload, qos=0, retain=False)
                _LOGGER.info("Sent batched keepalive to topic %s", topic)
            else:
                _LOGGER.warning(
                    "Cannot send keepalive - client or unique_id not available"
                )

        except Exception as err:
            _LOGGER.error("Error sending keepalive: %s", err)
        finally:
            self._keepalive_timer_handle = None

    def _add_entities_to_platforms(
        self, new_entities_by_platform: dict[str, list[Entity]]
    ) -> None:
        """Add entities to their respective platforms."""
        for platform, entities in new_entities_by_platform.items():
            if not entities:
                continue

            callback = self._platform_callbacks[platform]
            if callback:
                callback(entities)
            else:
                self._pending_entities[platform].extend(entities)

    async def _process_pending_via_device_entities(
        self, new_entities_by_platform: dict[str, list[Entity]]
    ) -> None:
        """Process entity configurations that were waiting for their via_device to become available."""
        if not self._pending_via_device_entities:
            return

        _LOGGER.info(
            "Processing %d pending via_device entity configs",
            len(self._pending_via_device_entities),
        )
        remaining_pending = []
        created_count = 0

        for component_cfg, unique_id, platform in self._pending_via_device_entities:
            # Get the via_device from the component's device info
            device_info = component_cfg.get("device")
            via_device_tuple = (
                _extract_via_device_from_discovery(device_info) if device_info else None
            )
            if via_device_tuple:
                _LOGGER.info(
                    "Checking deferred entity config %s (%s): via_device='%s'",
                    unique_id,
                    platform,
                    via_device_tuple,
                )

                if self._is_via_device_available(via_device_tuple):
                    # Via device is now available, create entity and add to platform
                    entity_factory = _PLATFORM_CONFIG[platform]["factory"]
                    entity = entity_factory(component_cfg, unique_id, self)
                    if entity:
                        if platform not in new_entities_by_platform:
                            new_entities_by_platform[platform] = []
                        new_entities_by_platform[platform].append(entity)
                        self._entity_registry[entity.unique_id] = entity
                        created_count += 1
                        _LOGGER.info(
                            "✅ CREATED and ADDING deferred entity %s (%s) to platform: via_device '%s' is now available",
                            unique_id,
                            platform,
                            via_device_tuple,
                        )
                else:
                    # Via device still not available, keep waiting
                    remaining_pending.append((component_cfg, unique_id, platform))
                    _LOGGER.debug(
                        "⏳ STILL WAITING for entity %s (%s): via_device '%s' not yet available",
                        unique_id,
                        platform,
                        via_device_tuple,
                    )
            else:
                # Entity config no longer has via_device dependency, create entity and add to platform
                entity_factory = _PLATFORM_CONFIG[platform]["factory"]
                entity = entity_factory(component_cfg, unique_id, self)
                if entity:
                    if platform not in new_entities_by_platform:
                        new_entities_by_platform[platform] = []
                    new_entities_by_platform[platform].append(entity)
                    self._entity_registry[entity.unique_id] = entity
                    created_count += 1
                    _LOGGER.info(
                        "CREATED and ADDING entity %s to platform (no longer has via_device dependency)",
                        unique_id,
                    )

        self._pending_via_device_entities = remaining_pending

        _LOGGER.info(
            "Pending entity processing complete: %d created and added to platforms, %d configs still waiting. Remaining configs: %s",
            created_count,
            len(remaining_pending),
            [(unique_id, p) for cfg, unique_id, p in remaining_pending],
        )

    async def _retry_pending_entities(self) -> None:
        """Periodically retry creating entities that are waiting for via_device dependencies."""
        max_retries = 10
        retry_count = 0

        while retry_count < max_retries:
            await asyncio.sleep(2)  # Wait 2 seconds between retries
            retry_count += 1

            async with self._via_device_lock:
                if not self._pending_via_device_entities:
                    _LOGGER.info(
                        "No more pending via_device entities, stopping retry task"
                    )
                    self._retry_pending_task = None
                    return

                _LOGGER.info(
                    "Retry %d/%d: Attempting to process %d pending via_device entities",
                    retry_count,
                    max_retries,
                    len(self._pending_via_device_entities),
                )

                new_entities_by_platform = {
                    platform: [] for platform in _PLATFORM_CONFIG
                }
                await self._process_pending_via_device_entities(
                    new_entities_by_platform
                )

            # Add any newly created entities outside the lock
            self._add_entities_to_platforms(new_entities_by_platform)
            for platform, entities in new_entities_by_platform.items():
                if entities:
                    _LOGGER.info(
                        "Added %d deferred %ss during retry", len(entities), platform
                    )

            # If no pending entities remain, we're done
            if not self._pending_via_device_entities:
                break

        if self._pending_via_device_entities:
            _LOGGER.error(
                "Failed to resolve %d via_device dependencies after %d retries: %s",
                len(self._pending_via_device_entities),
                max_retries,
                [
                    (unique_id, p)
                    for cfg, unique_id, p in self._pending_via_device_entities
                ],
            )

        self._retry_pending_task = None

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

    def request_device_rediscovery(self) -> None:
        """Request rediscovery of all devices by reconnecting MQTT."""
        _LOGGER.info("Manual device rediscovery requested - reconnecting MQTT")
        self.reconnect_mqtt()

    def set_platforms_setup_complete(self) -> None:
        """Mark that all platforms have been set up and send initial keepalive."""
        self._platforms_setup_complete = True
        # Restore devices from HA device registry first, then send keepalive
        self.hass.loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self._restore_devices_from_registry())
        )

    async def _restore_devices_from_registry(self) -> None:
        """Restore devices from Home Assistant's device registry on startup."""
        _LOGGER.info("Restoring devices from Home Assistant device registry")

        device_registry = dr.async_get(self.hass)

        # Find all devices associated with this integration
        devices = dr.async_entries_for_config_entry(
            device_registry, self.entry.entry_id
        )

        restored_count = 0

        for device in devices:
            # Extract the device identifier from identifiers
            device_identifiers = None
            for identifier_set in device.identifiers:
                if identifier_set[0] == DOMAIN:  # Our domain
                    device_identifiers = [
                        identifier_set[1]
                    ]  # Store as list for consistency
                    break

            if not device_identifiers:
                _LOGGER.warning(
                    "Device %s has no valid identifiers for domain %s, skipping restoration",
                    device.name,
                    DOMAIN,
                )
                continue

            # Create device info structure from registry data
            device_info = {
                "identifiers": device_identifiers,
                "name": device.name,
                "model": device.model,
                "manufacturer": device.manufacturer,
                "sw_version": device.sw_version,
                "hw_version": device.hw_version,
            }

            # Add via_device if it exists
            if device.via_device_id:
                # Find the via_device in the registry
                via_device = device_registry.async_get(device.via_device_id)
                if via_device:
                    # Extract via_device identifier
                    _LOGGER.debug("Via device identifiers: %s", via_device.identifiers)
                    for identifier_set in via_device.identifiers:
                        _LOGGER.debug(
                            "Checking identifier_set: %s (type: %s)",
                            identifier_set,
                            type(identifier_set),
                        )
                        if identifier_set[0] == DOMAIN:
                            via_device_id = identifier_set[1]
                            _LOGGER.debug(
                                "Extracted via_device_id: %s (type: %s)",
                                via_device_id,
                                type(via_device_id),
                            )
                            device_info["via_device"] = str(via_device_id)
                            break

            # Store restored device info in our local registry
            self._store_device_info(device_info)
            restored_count += 1

            _LOGGER.debug(
                "Restored device from registry: %s (identifiers: %s, via_device: %s)",
                device.name,
                device_identifiers,
                device_info.get("via_device"),
            )

        _LOGGER.info(
            "Restored %d devices from Home Assistant device registry. "
            "Entities will be created when MQTT discovery messages are received.",
            restored_count,
        )

    def reconnect_mqtt(self) -> None:
        """Reconnect MQTT to receive all retained discovery messages."""
        if not self.client:
            _LOGGER.warning("Cannot reconnect - no MQTT client available")
            return

        _LOGGER.info("Reconnecting MQTT to receive retained discovery messages")

        # Disconnect and reconnect in background thread
        def _reconnect():
            try:
                self.client.disconnect()
                _LOGGER.debug("Disconnected from MQTT broker")

                # Clear connection state
                self._connected.clear()

                # Reconnect (this will trigger _on_connect and resubscribe)
                broker = self.entry.data[CONF_BROKER]
                port = self.entry.data[CONF_PORT]
                self.client.connect(broker, port, 60)
                _LOGGER.info("Initiated MQTT reconnection to %s:%d", broker, port)
            except Exception as err:
                _LOGGER.error("Failed to reconnect MQTT: %s", err)

        # Run reconnection in executor to avoid blocking
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _reconnect)

    async def cleanup(self) -> None:
        """Clean up resources when the manager is being destroyed."""
        _LOGGER.info("Cleaning up VictronMqttManager resources")

        # Cancel any running retry tasks
        if self._retry_pending_task and not self._retry_pending_task.done():
            _LOGGER.debug("Cancelling retry pending task")
            self._retry_pending_task.cancel()
            try:
                await self._retry_pending_task
            except asyncio.CancelledError:
                pass
            self._retry_pending_task = None

        # Cancel any running keepalive timer
        if self._keepalive_timer_handle:
            _LOGGER.debug("Cancelling keepalive timer")
            self._keepalive_timer_handle.cancel()
            self._keepalive_timer_handle = None

        # Clear all registries
        registries_to_clear = [
            self._entity_registry,
            self._device_registry,
            self._pending_via_device_entities,
            self._topic_entity_map,
            self._subscribed_topics,
        ]
        for registry in registries_to_clear:
            registry.clear()

        # Clear pending entities for all platforms
        for pending_list in self._pending_entities.values():
            pending_list.clear()

        # Disconnect MQTT if still connected
        if self.client:
            try:
                self.client.disconnect()
                self.client.loop_stop()
            except Exception as err:
                _LOGGER.debug("Error during MQTT cleanup: %s", err)
            self.client = None

        _LOGGER.debug("VictronMqttManager cleanup completed")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Victron Energy from a config entry."""
    try:
        manager = VictronMqttManager(hass, entry)
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
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
    manager: VictronMqttManager = hass.data[DOMAIN].pop(entry.entry_id)

    # Clean up all manager resources
    await manager.cleanup()

    _LOGGER.info(
        "Victron Energy integration unloaded successfully for entry %s", entry.entry_id
    )
    return True
