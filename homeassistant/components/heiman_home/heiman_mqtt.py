"""Heiman MQTT Client.

Handles MQTT communication with Heiman Cloud for real-time
device communication including property reading/writing and event handling.
Supports device events, child device management, and gateway operations.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import hashlib
import json
import logging
import socket
import ssl
import time
from typing import Any

try:
    import paho.mqtt.client as mqtt

    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False
    mqtt = None

from .const import (
    CONF_MQTT_BROKER,
    CONF_REGION,
    CONF_SECURE_ID,
    CONF_SECURE_KEY,
    CONF_USER_ID,
    DEFAULT_REGION,
    DEFAULT_SECURE_ID,
    DEFAULT_SECURE_KEY,
    MQTT_PORT_SSL,
    MQTT_PORT_TCP,
    MQTT_TOPIC_PROPERTIES_READ_REPLY,
    MQTT_TOPIC_PROPERTIES_REPORT,
    MQTT_TOPIC_PROPERTIES_WRITE_REPLY,
    REGIONS,
)

_LOGGER = logging.getLogger(__name__)


class HeimanMqttError(Exception):
    """Base exception for Heiman MQTT errors."""


class HeimanMqttClient:
    """Enhanced Heiman MQTT client with full event support."""

    def __init__(
        self,
        hass,
        cloud_client,
        entry_id: str,
        config: dict | None = None,
    ) -> None:
        """Initialize MQTT client."""
        if not PAHO_AVAILABLE:
            raise ImportError(
                "paho-mqtt is required. Install with: pip install paho-mqtt",
            )

        self._hass = hass
        self._cloud_client = cloud_client
        self._entry_id = entry_id
        self._config = config or {}

        # Get region settings
        region = config.get(CONF_REGION, DEFAULT_REGION) if config else DEFAULT_REGION
        region_config = REGIONS.get(region) or REGIONS.get(DEFAULT_REGION)

        # MQTT connection settings
        self._broker = (
            config.get(CONF_MQTT_BROKER, region_config["mqtt_broker"])
            if config
            else region_config["mqtt_broker"]
        )

        # Log region and broker selection
        _LOGGER.info(">>> MQTT Configuration:")
        _LOGGER.info(">>>   Selected Region: %s", region.upper())
        _LOGGER.info(">>>   MQTT Broker: %s", self._broker)

        # Auto-select port based on broker
        # Test broker (192.168.1.14) uses TCP port 1883
        # Production brokers (mqtt.heiman.cn, spmqtt.heiman.cn) use SSL port 1884
        if self._broker == "192.168.1.14":
            self._port = MQTT_PORT_TCP
            _LOGGER.info(">>>   Port: %s (TCP - Test Environment)", self._port)
        else:
            self._port = MQTT_PORT_SSL
            _LOGGER.info(">>>   Port: %s (SSL/TLS - Production)", self._port)

        # Get secure_id and secure_key from cloud_client
        # Priority: config parameter > cloud_client > defaults
        self._secure_id = (
            (config.get(CONF_SECURE_ID) if config else None)
            or self._cloud_client.secure_id
            or DEFAULT_SECURE_ID
        )
        self._secure_key = (
            (config.get(CONF_SECURE_KEY) if config else None)
            or self._cloud_client.secure_key
            or DEFAULT_SECURE_KEY
        )

        # Get user_id for app topic forwarding
        self._user_id = (
            config.get(CONF_USER_ID) if config else None
        ) or self._cloud_client.user_id
        _LOGGER.debug(">>> User ID for MQTT app topics: %s", self._user_id)

        # Get user display name for device control payload (nickName优先，否则email)
        self._user_display_name = self._cloud_client.user_display_name
        _LOGGER.debug(
            ">>> User Display Name for device control: %s", self._user_display_name
        )

        _LOGGER.debug(">>> Using secure_id: %s", self._secure_id)
        _LOGGER.debug(">>> Using secure_key length: %s", len(self._secure_key))

        # Use access token as client ID for user authentication
        # Validate credentials before setting them
        if not self._cloud_client.access_token:
            _LOGGER.error(">>> access_token is None or empty - cannot connect to MQTT")
            raise HeimanMqttError(
                "access_token is None or empty - authentication failed",
            )

        self._client_id = self._cloud_client.access_token

        # Validate secure_id and secure_key
        if not self._secure_id or not self._secure_key:
            _LOGGER.error(
                ">>> secure_id or secure_key is None or empty - cannot authenticate",
            )
            _LOGGER.error(">>> secure_id: '%s'", self._secure_id)
            _LOGGER.error(">>> secure_key: '%s'", self._secure_key)
            raise HeimanMqttError(
                "secure_id or secure_key is None or empty - authentication failed",
            )

        self._username = f"appid_{self._secure_id}"
        self._password = self._generate_password(self._secure_id, self._secure_key)

        # Log authentication info (sanitized)
        _LOGGER.info(">>> Authentication:")
        _LOGGER.info(
            ">>>   Client ID (first 30 chars): %s",
            (self._client_id[:30] if self._client_id else "None") + "...",
        )
        _LOGGER.info(
            ">>>   Client ID length: %s",
            (len(self._client_id) if self._client_id else 0),
        )
        _LOGGER.info(">>>   Username: %s", self._username)
        _LOGGER.info(">>>   Password (MD5): %s", self._password)
        _LOGGER.info(">>>   Secure ID: %s", self._secure_id)
        _LOGGER.info(">>>   Secure Key: %s", "*" * len(self._secure_key))

        # MQTT client
        self._client: mqtt.Client | None = None
        self._connected = False
        self._connecting = False
        self._should_reconnect = True

        # Message tracking for requests
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._request_timeout = 10  # seconds
        self._connection_timeout = 30  # seconds - increased for better reliability
        self._enable_ssl = True  # Enable SSL/TLS by default

        # Event callbacks
        self._property_callbacks: dict[str, list[Callable[[str, dict], None]]] = {}
        self._event_callbacks: dict[str, list[Callable[[str, dict], None]]] = {}
        self._device_callbacks: list[Callable[[str, str], None]] = []

        # Subscribed topics
        self._subscribed_topics: set[str] = set()

        # Event loop
        self._loop = asyncio.get_running_loop()

        # Coordinator reference for cache updates
        self._coordinator = None

    def _generate_password(self, secure_id: str, secure_key: str) -> str:
        """Generate MD5 password for authentication."""
        md5_str = f"{secure_id}|{secure_key}"
        return hashlib.md5(md5_str.encode("utf-8")).hexdigest()

    def _generate_message_id(self) -> str:
        """Generate a unique message ID."""
        return f"{int(time.time() * 1000)}"

    async def _check_network_connectivity(self) -> dict[str, bool]:
        """Check network connectivity to MQTT broker and DNS resolution.

        Note: This method runs blocking socket/SSL operations in an executor
        to avoid blocking the event loop.
        """
        _LOGGER.debug(">>> Checking network connectivity...")
        results = {
            "dns_resolution": False,
            "tcp_connection": False,
            "ssl_handshake": False,
        }

        def _check_sync():
            """Synchronous network check to run in executor."""
            nonlocal results
            try:
                # Check DNS resolution
                _LOGGER.debug(">>> Resolving DNS: %s", self._broker)
                addr_info = socket.getaddrinfo(self._broker, self._port)
                if addr_info:
                    results["dns_resolution"] = True
                    _LOGGER.debug(
                        ">>> DNS resolved successfully: %s", addr_info[0][4][0]
                    )

                # Check TCP connection
                _LOGGER.debug(
                    ">>> Checking TCP connection to %s:%s", self._broker, self._port
                )
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((self._broker, self._port))
                if result == 0:
                    results["tcp_connection"] = True
                    _LOGGER.debug(">>> TCP connection successful")
                else:
                    _LOGGER.debug(
                        ">>> TCP connection failed with error code: %s", result
                    )
                sock.close()

                # Check SSL handshake for SSL ports
                if self._port in (1884, 8883, 8884):
                    _LOGGER.debug(">>> Checking SSL/TLS handshake...")
                    try:
                        # Note: ssl.create_default_context() calls load_default_certs()
                        # which is a blocking operation - running in executor
                        context = ssl.create_default_context()
                        with (
                            socket.create_connection(
                                (self._broker, self._port),
                                timeout=5,
                            ) as sock,
                            context.wrap_socket(
                                sock,
                                server_hostname=self._broker,
                            ) as ssock,
                        ):
                            results["ssl_handshake"] = True
                            _LOGGER.debug(">>> SSL/TLS handshake successful")
                            _LOGGER.debug(">>> SSL version: %s", ssock.version())
                    except OSError as ssl_err:
                        _LOGGER.debug(">>> SSL/TLS handshake failed: %s", ssl_err)

            except OSError as err:
                _LOGGER.debug(">>> Network check error: %s", err)

        # Run blocking network check in executor
        await self._hass.async_add_executor_job(_check_sync)

        _LOGGER.debug(">>> Network check results: %s", results)
        return results

    async def async_connect(self) -> bool:
        """Connect to MQTT broker."""
        if self._connected or self._connecting:
            _LOGGER.debug("MQTT already connected or connecting")
            return True

        self._connecting = True

        try:
            _LOGGER.info("=" * 80)
            _LOGGER.info("Attempting to connect to MQTT broker")
            _LOGGER.info("=" * 80)
            _LOGGER.info(">>> MQTT Broker: %s", self._broker)
            _LOGGER.info(">>> MQTT Port: %s", self._port)
            _LOGGER.info(
                ">>> Client ID (first 20 chars): %s",
                (self._client_id[:20] if self._client_id else "None") + "...",
            )
            _LOGGER.info(">>> Username: %s", self._username)
            _LOGGER.info(
                ">>> Password (first 8 chars): %s",
                (self._password[:8] if self._password else "None") + "...",
            )

            # Create MQTT client
            self._client = mqtt.Client(
                client_id=self._client_id,
                protocol=mqtt.MQTTv311,
                transport="tcp",
            )

            # Enable SSL/TLS for SSL port (1884)
            if self._port == MQTT_PORT_SSL:
                _LOGGER.debug(">>> Configuring SSL/TLS connection")

                # Use executor for blocking TLS configuration
                # tls_set() calls set_default_verify_paths() which blocks the event loop
                def configure_tls():
                    self._client.tls_set(
                        ca_certs=None,  # Use system CA certificates
                        certfile=None,
                        keyfile=None,
                        cert_reqs=mqtt.ssl.CERT_REQUIRED,
                        tls_version=mqtt.ssl.PROTOCOL_TLS,
                        ciphers=None,
                    )
                    self._client.tls_insecure_set(False)

                await self._hass.async_add_executor_job(configure_tls)

            # Set callbacks
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message
            self._client.on_publish = self._on_publish

            # Set username/password
            self._client.username_pw_set(self._username, self._password)

            # Network diagnostics before connection
            _LOGGER.info(">>> Running network diagnostics...")
            net_results = await self._check_network_connectivity()
            _LOGGER.info(
                ">>> DNS Resolution: %s", "✓" if net_results["dns_resolution"] else "✗"
            )
            _LOGGER.info(
                ">>> TCP Connection: %s", "✓" if net_results["tcp_connection"] else "✗"
            )
            _LOGGER.info(
                ">>> SSL Handshake: %s", "✓" if net_results["ssl_handshake"] else "✗"
            )

            if not net_results["dns_resolution"]:
                _LOGGER.warning(">>> DNS resolution failed - check broker hostname")
            if not net_results["tcp_connection"]:
                _LOGGER.warning(">>> TCP connection failed - check network/firewall")
            if not net_results["ssl_handshake"] and self._port == MQTT_PORT_SSL:
                _LOGGER.warning(">>> SSL handshake failed - check SSL configuration")

            # Set connection parameters
            self._client.connect_async(self._broker, self._port, 60)

            # Start the network loop in a separate thread
            self._client.loop_start()

            _LOGGER.info(">>> MQTT client started, waiting for connection...")

            # Wait for connection with increased timeout (30 seconds)
            max_wait_time = 30  # seconds
            check_interval = 0.2  # seconds
            total_checks = int(max_wait_time / check_interval)

            for i in range(total_checks):
                if self._connected:
                    elapsed_time = (i + 1) * check_interval
                    _LOGGER.info(
                        ">>> MQTT connected successfully after %.1f seconds",
                        elapsed_time,
                    )
                    break
                if i % 50 == 0 and i > 0:  # Log every 10 seconds
                    elapsed_time = i * check_interval
                    _LOGGER.debug(
                        ">>> Still connecting... (%.1fs elapsed)", elapsed_time
                    )
                await asyncio.sleep(check_interval)

            if not self._connected:
                _LOGGER.error("=" * 80)
                _LOGGER.error("MQTT CONNECTION TIMEOUT")
                _LOGGER.error("=" * 80)
                _LOGGER.error(">>> Broker: %s:%s", self._broker, self._port)
                _LOGGER.error(">>> Timeout after: %s seconds", max_wait_time)
                _LOGGER.error(">>> Possible causes:")
                _LOGGER.error(">>>   1. MQTT broker is unreachable (network/firewall)")
                _LOGGER.error(">>>   2. Invalid broker address or port")
                _LOGGER.error(">>>   3. SSL/TLS handshake failed")
                _LOGGER.error(">>>   4. Authentication credentials invalid")
                _LOGGER.error(">>>   5. Client ID conflict")
                _LOGGER.info("=" * 80)
                raise HeimanMqttError(
                    f"Connection timeout after {max_wait_time}s to {self._broker}:{self._port}",
                )

            _LOGGER.info("=" * 80)
            _LOGGER.info("MQTT connection established successfully")
            _LOGGER.info("=" * 80)

        except (OSError, RuntimeError, ValueError) as err:
            _LOGGER.error("=" * 80)
            _LOGGER.error("MQTT CONNECTION FAILED")
            _LOGGER.error("=" * 80)
            _LOGGER.error(">>> Error: %s", type(err).__name__)
            _LOGGER.error(">>> Message: %s", err)
            _LOGGER.exception(">>> Full exception")
            _LOGGER.info("=" * 80)
            self._connecting = False
            raise HeimanMqttError(f"Connection failed: {err}") from err
        else:
            return True

    def _on_connect(self, client, userdata, flags, rc) -> None:
        """Called when MQTT client connects."""
        if rc == 0:
            self._connected = True
            self._connecting = False
            _LOGGER.info("MQTT client connected")

            # Subscribe to unified app topic with wildcard
            # This handles all device messages under /iot/app/11/{user_id}/
            if self._user_id:
                app_topic = f"/iot/app/11/{self._user_id}/#"
                client.subscribe(app_topic)
                self._subscribed_topics.add(app_topic)
                _LOGGER.info("Subscribed to app topic: %s", app_topic)
            else:
                _LOGGER.warning(
                    "User ID not available, falling back to per-device subscription",
                )
                # Fallback: Subscribe to topics for all devices (original logic)
                for device_id, device_info in self._cloud_client.devices.items():
                    product_id = device_info.get("productId", "")
                    if product_id:
                        topic = MQTT_TOPIC_PROPERTIES_REPORT.format(
                            product_id=product_id,
                            device_id=device_id,
                        )
                        client.subscribe(topic)
                        self._subscribed_topics.add(topic)
                        _LOGGER.debug("Subscribed to topic: %s", topic)

                        # Subscribe to reply topics
                        read_reply_topic = MQTT_TOPIC_PROPERTIES_READ_REPLY.format(
                            product_id=product_id,
                            device_id=device_id,
                        )
                        client.subscribe(read_reply_topic)
                        self._subscribed_topics.add(read_reply_topic)

                        write_reply_topic = MQTT_TOPIC_PROPERTIES_WRITE_REPLY.format(
                            product_id=product_id,
                            device_id=device_id,
                        )
                        client.subscribe(write_reply_topic)
                        self._subscribed_topics.add(write_reply_topic)

                        # Subscribe to event topics
                        event_topic = f"/{product_id}/{device_id}/event/post"
                        client.subscribe(event_topic)
                        self._subscribed_topics.add(event_topic)

                        # Subscribe to child device topics
                        child_register_topic = (
                            f"/{product_id}/{device_id}/child/+/register"
                        )
                        client.subscribe(child_register_topic)
                        self._subscribed_topics.add(child_register_topic)

                        child_online_topic = f"/{product_id}/{device_id}/child/+/online"
                        client.subscribe(child_online_topic)
                        self._subscribed_topics.add(child_online_topic)

                        child_offline_topic = (
                            f"/{product_id}/{device_id}/child/+/offline"
                        )
                        client.subscribe(child_offline_topic)
                        self._subscribed_topics.add(child_offline_topic)

                        topo_reply_topic = f"/{product_id}/{device_id}/topo/get_reply"
                        client.subscribe(topo_reply_topic)
                        self._subscribed_topics.add(topo_reply_topic)
        else:
            _LOGGER.error("=" * 80)
            _LOGGER.error("MQTT connection failed with code %s", rc)
            _LOGGER.error("=" * 80)
            self._connected = False
            self._connecting = False

            # Detailed error explanation
            error_messages = {
                0: "Connection accepted",
                1: "Connection refused: unacceptable protocol version",
                2: "Connection refused: identifier rejected",
                3: "Connection refused: server unavailable",
                4: "Connection refused: bad user name or password",
                5: "Connection refused: not authorized",
            }
            _LOGGER.error(
                ">>> Error meaning: %s", error_messages.get(rc, "Unknown error")
            )

            if rc in [4, 5]:
                _LOGGER.error(">>> Authentication failed! Possible causes:")
                _LOGGER.error(">>>   1. Invalid access_token (expired or revoked)")
                _LOGGER.error(">>>   2. Incorrect secure_id or secure_key")
                _LOGGER.error(">>>   3. Client ID already in use")
                _LOGGER.error(">>>   4. Username/password mismatch")
                _LOGGER.error(">>>   Current secure_id: %s", self._secure_id)
                _LOGGER.error(
                    ">>>   Current secure_key: %s", "*" * len(self._secure_key)
                )

            _LOGGER.error("=" * 80)

    def _on_disconnect(self, client, userdata, rc) -> None:
        """Called when MQTT client disconnects."""
        self._connected = False
        _LOGGER.info("MQTT client disconnected (rc=%s)", rc)

        # Reconnect if needed
        if self._should_reconnect and rc != 0:
            _LOGGER.info("Attempting to reconnect...")
            try:
                client.reconnect()
            except (OSError, RuntimeError, ValueError) as err:
                _LOGGER.error("Reconnect failed: %s", err)

    def _on_message(self, client, userdata, msg) -> None:
        """Called when a message is received."""
        try:
            topic = msg.topic
            raw_payload = msg.payload.decode("utf-8")
            payload = json.loads(raw_payload)

            # 打印接收到的 MQTT 数据
            _LOGGER.info("=" * 60)
            _LOGGER.info("[MQTT RECEIVED] 主题: %s", topic)
            _LOGGER.info("[MQTT RECEIVED] 原始数据: %s", raw_payload)
            _LOGGER.info("[MQTT RECEIVED] 解析数据: %s", payload)
            _LOGGER.info("=" * 60)

            # Parse topic to extract device info from app topics
            # Format: /iot/app/11/{user_id}/{product_id}/{device_id}/...
            # Or original format: /{product_id}/{device_id}/...
            topic_parts = topic.split("/")

            # Determine actual topic suffix based on topic format
            if (
                len(topic_parts) >= 4
                and topic_parts[1] == "iot"
                and topic_parts[2] == "app"
            ):
                # App topic format: /iot/app/11/{user_id}/{product_id}/{device_id}/...
                # Extract suffix after user_id (index 4)
                if len(topic_parts) > 5:
                    actual_suffix = "/" + "/".join(topic_parts[5:])
                else:
                    actual_suffix = ""
            else:
                # Original format: /{product_id}/{device_id}/...
                actual_suffix = (
                    "/" + "/".join(topic_parts[2:]) if len(topic_parts) > 2 else topic
                )

            # Handle property report
            if "/properties/report" in actual_suffix:
                self._handle_property_report(topic, payload)

            # Handle read/write replies
            elif "/properties/read/reply" in actual_suffix:
                self._handle_read_reply(topic, payload)
            elif "/properties/write/reply" in actual_suffix:
                self._handle_write_reply(topic, payload)

            # Handle events (match any /event/... topic, not just /event/post)
            # Check this BEFORE child device topics to handle child device events correctly
            elif "/event/" in actual_suffix:
                _LOGGER.info("Routing message to event handler from topic: %s", topic)
                self._handle_event(topic, payload)

            # Handle child device registration/unregistration
            elif "/child/" in actual_suffix and "/register" in actual_suffix:
                if actual_suffix.endswith("/register"):
                    self._handle_child_register(topic, payload)
                elif actual_suffix.endswith("/register_reply"):
                    self._handle_child_register_reply(topic, payload)

            # Handle child device online/offline
            elif "/child/" in actual_suffix and (
                "/online" in actual_suffix or "/offline" in actual_suffix
            ):
                if actual_suffix.endswith("/online"):
                    self._handle_child_online(topic, payload)
                elif actual_suffix.endswith("/offline"):
                    self._handle_child_offline(topic, payload)

            # Handle topology query reply
            elif "/topo/get_reply" in actual_suffix:
                self._handle_topo_get_reply(topic, payload)

        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to parse MQTT message: %s", err)
        except (ValueError, KeyError, TypeError, RuntimeError) as err:
            _LOGGER.error("Error handling MQTT message: %s", err)

    def _on_publish(self, client, userdata, mid) -> None:
        """Called when a message is published."""
        _LOGGER.debug("Message published: %s", mid)

    def set_coordinator(self, coordinator) -> None:
        """Set coordinator reference for cache updates."""
        self._coordinator = coordinator
        _LOGGER.debug("MQTT client coordinator reference set")

    def _handle_property_report(self, topic: str, payload: dict) -> None:
        """Handle device property report."""
        try:
            device_id = payload.get("deviceId")
            properties = payload.get("properties", {})

            if device_id and properties:
                _LOGGER.info("Property report for %s: %s", device_id, properties)

                # Update coordinator cache if available
                if self._coordinator:
                    self._coordinator.update_device_properties(device_id, properties)
                    _LOGGER.debug("Updated coordinator cache for %s", device_id)

                # Call registered property callbacks
                for prop_name, prop_value in properties.items():
                    callbacks = self._property_callbacks.get(prop_name, [])
                    for callback in callbacks:
                        try:
                            callback(device_id, {prop_name: prop_value})
                        except (ValueError, KeyError, TypeError, RuntimeError) as err:
                            _LOGGER.error("Error in property callback: %s", err)

                # Call device callbacks
                for callback in self._device_callbacks:
                    try:
                        callback(device_id, "property_report")
                    except (ValueError, KeyError, TypeError, RuntimeError) as err:
                        _LOGGER.error("Error in device callback: %s", err)

        except (ValueError, KeyError, TypeError, RuntimeError, OSError) as err:
            _LOGGER.error("Error handling property report: %s", err)

    def _handle_read_reply(self, topic: str, payload: dict) -> None:
        """Handle read property reply."""
        try:
            message_id = payload.get("messageId")
            if message_id and message_id in self._pending_requests:
                future = self._pending_requests.pop(message_id)
                if not future.done():
                    if payload.get("success"):
                        future.set_result(payload.get("properties"))
                    else:
                        future.set_exception(
                            HeimanMqttError(payload.get("code", "Read failed")),
                        )
        except (ValueError, KeyError, TypeError, RuntimeError) as err:
            _LOGGER.error("Error handling read reply: %s", err)

    def _handle_write_reply(self, topic: str, payload: dict) -> None:
        """Handle write property reply."""
        try:
            message_id = payload.get("messageId")
            device_id = payload.get("deviceId")
            properties = payload.get("properties", {})
            success = payload.get("success", 0)

            _LOGGER.debug(
                "Write reply received: device=%s, properties=%s, success=%s",
                device_id,
                properties,
                success,
            )

            # If successful and we have device_id and properties, update coordinator cache
            if success and device_id and properties and self._coordinator:
                # Update coordinator cache with the new values
                self._coordinator.update_device_properties(device_id, properties)
                _LOGGER.info(
                    "Updated coordinator cache from write reply for device %s: %s",
                    device_id,
                    properties,
                )

            # Handle pending request future
            if message_id and message_id in self._pending_requests:
                future = self._pending_requests.pop(message_id)
                if not future.done():
                    if payload.get("success"):
                        future.set_result(True)
                    else:
                        future.set_exception(
                            HeimanMqttError(payload.get("code", "Write failed")),
                        )
        except (ValueError, KeyError, TypeError, RuntimeError) as err:
            _LOGGER.error("Error handling write reply: %s", err)

    def _handle_event(self, topic: str, payload: dict) -> None:
        """Handle device event."""
        try:
            event_type = payload.get("eventType")
            device_id = payload.get("deviceId")
            event_data = payload.get("data", {})

            if device_id:
                _LOGGER.info(
                    "Event %s from device %s: %s", event_type, device_id, event_data
                )

                # Update coordinator cache with event data if available
                # Event data often contains sensor states like {"SmokeSensorState": 1}
                if self._coordinator and event_data:
                    self._coordinator.update_device_properties(device_id, event_data)
                    _LOGGER.debug(
                        "Updated coordinator cache from event for %s", device_id
                    )

                # Call registered event callbacks
                # First, call callbacks for specific event type
                if event_type:
                    callbacks = self._event_callbacks.get(event_type, [])
                    _LOGGER.debug(
                        "Found %s callbacks for specific event type: %s",
                        len(callbacks),
                        event_type,
                    )
                    for callback in callbacks:
                        try:
                            callback(device_id, payload)
                        except (ValueError, KeyError, TypeError, RuntimeError) as err:
                            _LOGGER.error(
                                "Error in event callback for %s: %s", event_type, err
                            )

                # Then, call callbacks that listen to all events
                all_callbacks = self._event_callbacks.get("__all__", [])
                _LOGGER.info("Found %s global event callbacks", len(all_callbacks))
                for idx, callback in enumerate(all_callbacks):
                    try:
                        _LOGGER.debug(
                            "Calling global event callback %s/%s for device %s",
                            idx + 1,
                            len(all_callbacks),
                            device_id,
                        )
                        callback(device_id, payload)
                    except ValueError, KeyError, TypeError, RuntimeError:
                        _LOGGER.exception("Error in global event callback")

                # Call device callbacks
                _LOGGER.debug(
                    "Calling %s device callbacks", len(self._device_callbacks)
                )
                for callback in self._device_callbacks:
                    try:
                        callback(device_id, f"event:{event_type}")
                    except (ValueError, KeyError, TypeError, RuntimeError) as err:
                        _LOGGER.error("Error in device callback: %s", err)

        except ValueError, KeyError, TypeError, RuntimeError, OSError:
            _LOGGER.exception("Error handling event")

    def _handle_child_register(self, topic: str, payload: dict) -> None:
        """Handle child device registration."""
        try:
            device_id = payload.get("deviceId")
            headers = payload.get("headers", {})

            if device_id:
                _LOGGER.info(
                    "Child device registered: %s, headers: %s", device_id, headers
                )

                # Extract child device info from headers
                headers.get("productId")
                headers.get("deviceName")
                headers.get("name")

                # Notify coordinator to refresh device list
                if self._coordinator:
                    # Schedule a refresh to fetch the new device
                    self._coordinator.schedule_refresh()
                    _LOGGER.debug(
                        "Scheduled coordinator refresh for new child device %s",
                        device_id,
                    )

                # Call device callbacks
                for callback in self._device_callbacks:
                    try:
                        callback(device_id, "child_register")
                    except (ValueError, KeyError, TypeError, RuntimeError) as err:
                        _LOGGER.error("Error in child register callback: %s", err)

        except (ValueError, KeyError, TypeError, RuntimeError, OSError) as err:
            _LOGGER.error("Error handling child register: %s", err)

    def _handle_child_register_reply(self, topic: str, payload: dict) -> None:
        """Handle child device registration reply."""
        try:
            message_id = payload.get("messageId")
            if message_id and message_id in self._pending_requests:
                future = self._pending_requests.pop(message_id)
                if not future.done():
                    if payload.get("success", True):
                        future.set_result(payload)
                    else:
                        future.set_exception(
                            HeimanMqttError(payload.get("code", "Register failed")),
                        )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error handling child register reply: %s", err)

    def _handle_child_online(self, topic: str, payload: dict) -> None:
        """Handle child device online."""
        try:
            device_id = payload.get("deviceId")
            headers = payload.get("headers", {})

            if device_id:
                _LOGGER.info("Child device online: %s, headers: %s", device_id, headers)

                # Update coordinator cache
                if self._coordinator:
                    # Mark device as online in cache via coordinator API
                    self._coordinator.update_device_properties(
                        device_id, {"online": True}
                    )
                    self._coordinator.schedule_refresh()
                    _LOGGER.debug(
                        "Scheduled coordinator refresh for online child device %s",
                        device_id,
                    )

                # Call device callbacks
                for callback in self._device_callbacks:
                    try:
                        callback(device_id, "child_online")
                    except (ValueError, KeyError, TypeError, RuntimeError) as err:
                        _LOGGER.error("Error in child online callback: %s", err)

        except (ValueError, KeyError, TypeError, RuntimeError, OSError) as err:
            _LOGGER.error("Error handling child online: %s", err)

    def _handle_child_offline(self, topic: str, payload: dict) -> None:
        """Handle child device offline."""
        try:
            device_id = payload.get("deviceId")

            if device_id:
                _LOGGER.info("Child device offline: %s", device_id)

                # Update coordinator cache
                if self._coordinator:
                    # Mark device as offline in cache via coordinator API
                    self._coordinator.update_device_properties(
                        device_id, {"online": False}
                    )
                    self._coordinator.schedule_refresh()
                    _LOGGER.debug(
                        "Scheduled coordinator refresh for offline child device %s",
                        device_id,
                    )

                # Call device callbacks
                for callback in self._device_callbacks:
                    try:
                        callback(device_id, "child_offline")
                    except (ValueError, KeyError, TypeError, RuntimeError) as err:
                        _LOGGER.error("Error in child offline callback: %s", err)

        except (ValueError, KeyError, TypeError, RuntimeError, OSError) as err:
            _LOGGER.error("Error handling child offline: %s", err)

    def _handle_topo_get_reply(self, topic: str, payload: dict) -> None:
        """Handle topology query reply."""
        try:
            message_id = payload.get("messageId")
            data = payload.get("data", [])
            continue_flag = payload.get("continue", 0)

            if message_id and message_id in self._pending_requests:
                future = self._pending_requests.pop(message_id)
                if not future.done():
                    if data:
                        _LOGGER.info(
                            "Topology query reply: %s child devices, continue: %s",
                            len(data),
                            continue_flag,
                        )
                        future.set_result({"devices": data, "continue": continue_flag})
                    else:
                        future.set_exception(HeimanMqttError("No child devices found"))
        except (ValueError, KeyError, TypeError, RuntimeError) as err:
            _LOGGER.error("Error handling topology query reply: %s", err)

    def register_property_callback(
        self,
        property_name: str,
        callback: Callable[[str, dict], None],
    ) -> None:
        """Register a callback for property updates."""
        if property_name not in self._property_callbacks:
            self._property_callbacks[property_name] = []
        self._property_callbacks[property_name].append(callback)
        _LOGGER.debug("Registered callback for property: %s", property_name)

    def unregister_property_callback(
        self,
        property_name: str,
        callback: Callable[[str, dict], None],
    ) -> None:
        """Unregister a property callback."""
        if property_name in self._property_callbacks:
            if callback in self._property_callbacks[property_name]:
                self._property_callbacks[property_name].remove(callback)
        _LOGGER.debug("Unregistered callback for property: %s", property_name)

    def register_event_callback(
        self,
        event_type: str | None,
        callback: Callable[[str, dict], None],
    ) -> None:
        """Register a callback for events.

        Args:
            event_type: Event type to listen for. If None, listens to all events.
            callback: Callback function to register
        """
        if event_type is None:
            # Special key for global event listeners
            event_type = "__all__"

        if event_type not in self._event_callbacks:
            self._event_callbacks[event_type] = []
        self._event_callbacks[event_type].append(callback)
        _LOGGER.info(
            "Registered callback for event: %s, total callbacks: %s",
            event_type,
            len(self._event_callbacks[event_type]),
        )

    def unregister_event_callback(
        self,
        event_type: str | None,
        callback: Callable[[str, dict], None],
    ) -> None:
        """Unregister an event callback."""
        if event_type is None:
            event_type = "__all__"

        if event_type in self._event_callbacks:
            if callback in self._event_callbacks[event_type]:
                self._event_callbacks[event_type].remove(callback)
                _LOGGER.debug("Unregistered callback for event: %s", event_type)

    def register_device_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register a callback for device state changes."""
        self._device_callbacks.append(callback)
        _LOGGER.debug("Registered device state callback")

    async def async_read_property(
        self,
        product_id: str,
        device_id: str,
        property_name: str,
    ) -> dict | None:
        """Read a device property via MQTT."""
        if not self._connected or not self._client:
            _LOGGER.warning("MQTT not connected, cannot read property")
            return None

        try:
            topic = f"/{product_id}/{device_id}/properties/read"
            message_id = self._generate_message_id()

            payload = {
                "timestamp": int(time.time() * 1000),
                "messageId": message_id,
                "deviceId": device_id,
                "properties": [property_name],
            }

            # Create future for response
            future = asyncio.Future()
            self._pending_requests[message_id] = future

            # Publish to original topic with error handling
            try:
                await self._loop.run_in_executor(
                    None,
                    lambda: self._safe_publish(topic, json.dumps(payload), qos=1),
                )
            except (OSError, RuntimeError, ValueError) as pub_err:
                _LOGGER.debug(
                    "Failed to publish read request to topic %s: %s", topic, pub_err
                )
                self._pending_requests.pop(message_id, None)
                return None

            # # Also publish to app topic if user_id is available
            # if self._user_id:
            #     app_topic = f"/iot/app/11/{self._user_id}{topic}"
            #     try:
            #         await self._loop.run_in_executor(
            #             None,
            #             lambda: self._safe_publish(
            #                 app_topic,
            #                 json.dumps(payload),
            #                 qos=1
            #             )
            #         )
            #         _LOGGER.debug(f"Published read request to app topic: {app_topic}")
            #     except Exception as app_pub_err:
            #         _LOGGER.debug(f"Failed to publish to app topic {app_topic}: {app_pub_err}")

            # Wait for response
            try:
                result = await asyncio.wait_for(future, timeout=self._request_timeout)
                return (
                    {property_name: result.get(property_name)}
                    if isinstance(result, dict)
                    else None
                )
            except TimeoutError:
                self._pending_requests.pop(message_id, None)
                _LOGGER.warning("Read property timeout: %s", property_name)
                return None

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to read property %s: %s", property_name, err)
            return None

    def _is_child_device(self, device_info: dict | None) -> bool:
        """Check if device is a child device (gateway sub-device).

        Args:
            device_info: Device information dictionary

        Returns:
            True if device is a child device, False otherwise
        """
        if not device_info:
            return False

        device_type = device_info.get("deviceType")
        if isinstance(device_type, dict):
            return device_type.get("value") == "childrenDevice"
        return False

    def _build_write_topic(
        self,
        product_id: str,
        device_id: str,
        device_info: dict | None,
    ) -> str:
        """Build MQTT topic for writing device properties.

        For child devices (gateway sub-devices), the topic format is:
        /{parentProductId}/{parentDeviceId}/child/{childDeviceId}/properties/write

        For regular devices, the topic format is:
        /{product_id}/{device_id}/properties/write

        Args:
            product_id: Device product ID
            device_id: Device ID
            device_info: Device information dictionary

        Returns:
            MQTT topic string
        """
        _LOGGER.info(
            "[CHILD-DEVICE] Building write topic for device %s, product %s, "
            "device_info keys: %s",
            device_id,
            product_id,
            list(device_info.keys()) if device_info else None,
        )

        if self._is_child_device(device_info):
            # Get parent device info
            parent_id = device_info.get("parentId")

            _LOGGER.info(
                "[CHILD-DEVICE] Device %s is child device, parent_id: %s",
                device_id,
                parent_id,
            )

            if parent_id:
                # Get parent device info from cloud client
                parent_device = None
                parent_product_id = None

                _LOGGER.info(
                    "[CHILD-DEVICE] Checking cloud_client: exists=%s, has devices=%s",
                    hasattr(self, "_cloud_client") and self._cloud_client is not None,
                    hasattr(self._cloud_client, "devices")
                    if hasattr(self, "_cloud_client") and self._cloud_client
                    else False,
                )

                if hasattr(self, "_cloud_client") and self._cloud_client:
                    devices = self._cloud_client.devices
                    _LOGGER.info(
                        "[CHILD-DEVICE] Cloud client devices count: %d, device IDs: %s",
                        len(devices),
                        list(devices.keys()),  # Show first 10 device IDs
                    )

                    parent_device = devices.get(parent_id)
                    _LOGGER.info(
                        "[CHILD-DEVICE] Looking for parent device %s: found=%s",
                        parent_id,
                        parent_device is not None,
                    )

                    if parent_device:
                        _LOGGER.info(
                            "[CHILD-DEVICE] Parent device %s info: %s",
                            parent_id,
                            parent_device,
                        )
                        parent_product_id = parent_device.get("productId")
                        _LOGGER.info(
                            "[CHILD-DEVICE] Parent product ID: %s",
                            parent_product_id,
                        )

                if parent_product_id:
                    # Child device topic format
                    # /{parentProductId}/{parentDeviceId}/child/{childDeviceId}/properties/write
                    topic = f"/{parent_product_id}/{parent_id}/child/{product_id}/properties/write"
                    _LOGGER.info(
                        "[CHILD-DEVICE] Using child device topic for %s: %s (parent: %s)",
                        device_id,
                        topic,
                        parent_id,
                    )
                    return topic
                _LOGGER.warning(
                    "[CHILD-DEVICE] Child device %s has parent %s but parent product ID not found, "
                    "falling back to regular topic. parent_device=%s",
                    device_id,
                    parent_id,
                    parent_device,
                )
        else:
            device_type = device_info.get("deviceType") if device_info else None
            _LOGGER.info(
                "[CHILD-DEVICE] Device %s is NOT child device, deviceType: %s",
                device_id,
                device_type,
            )

        # Regular device topic format
        topic = f"/{product_id}/{device_id}/properties/write"
        _LOGGER.info("[CHILD-DEVICE] Using regular topic for %s: %s", device_id, topic)
        return topic

    async def async_write_property(
        self,
        product_id: str,
        device_id: str,
        property_name: str,
        value: Any,
        device_info: dict | None = None,
    ) -> bool:
        """Write a device property via MQTT.

        Args:
            product_id: Device product ID
            device_id: Device ID
            property_name: Property name to write
            value: Value to write
            device_info: Optional device info to determine if it's a child device

        Returns:
            True if successful, False otherwise
        """
        if not self._connected or not self._client:
            _LOGGER.warning("MQTT not connected, cannot write property")
            return False

        try:
            # Build topic based on device type (child or regular)
            topic = self._build_write_topic(product_id, device_id, device_info)
            message_id = self._generate_message_id()

            # Convert boolean values to integers (0/1) for compatibility
            # Some devices expect integers instead of boolean JSON values
            if isinstance(value, bool):
                converted_value = 1 if value else 0
                _LOGGER.debug(
                    "Converting boolean value %s to integer %s for property %s",
                    value,
                    converted_value,
                    property_name,
                )
            # Convert string numbers to integers for properties that expect numeric values
            # This handles cases like AlarmSoundOption where value is "0", "1", "2" but device expects int
            elif isinstance(value, str) and value.isdigit():
                converted_value = int(value)
                _LOGGER.debug(
                    "Converting string number '%s' to integer %s for property %s",
                    value,
                    converted_value,
                    property_name,
                )
            else:
                converted_value = value

            # Build properties with UserName if available
            properties_payload = {property_name: converted_value}
            if self._user_display_name:
                properties_payload["UserName"] = self._user_display_name

            payload = {
                "timestamp": int(time.time() * 1000),
                "messageId": message_id,
                "deviceId": device_id,
                "properties": properties_payload,
                "messageType": "WRITE_PROPERTY",
            }

            # Create future for response
            future = asyncio.Future()
            self._pending_requests[message_id] = future
            _LOGGER.info("Write property topic: %s payload: %s", topic, payload)
            # Publish to original topic with error handling
            try:
                await self._loop.run_in_executor(
                    None,
                    lambda: self._safe_publish(topic, json.dumps(payload), qos=1),
                )
            except Exception as pub_err:  # noqa: BLE001
                _LOGGER.debug(
                    "Failed to publish read request to topic %s: %s",
                    topic,
                    pub_err,
                )
                self._pending_requests.pop(message_id, None)
                return None

            # Wait for response
            try:
                await asyncio.wait_for(future, timeout=self._request_timeout)
            except TimeoutError:
                self._pending_requests.pop(message_id, None)
                _LOGGER.warning("Write property timeout: %s", property_name)
                return False
            else:
                return True

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to write property %s: %s", property_name, err)
            return False

    async def async_query_topology(
        self,
        product_id: str,
        device_id: str,
    ) -> dict | None:
        """Query child device topology from gateway.

        Args:
            product_id: Gateway product ID
            device_id: Gateway device ID

        Returns:
            Dict with child devices list or None if failed
        """
        if not self._connected or not self._client:
            _LOGGER.warning("MQTT not connected, cannot query topology")
            return None

        try:
            topic = f"/{product_id}/{device_id}/topo/get"
            message_id = self._generate_message_id()

            payload = {
                "timestamp": int(time.time() * 1000),
                "messageId": message_id,
                "deviceId": device_id,
                "batchSize": 100,  # Request up to 100 devices per packet
            }

            # Create future for response
            future = asyncio.Future()
            self._pending_requests[message_id] = future

            # Publish query
            await self._loop.run_in_executor(
                None,
                lambda: self._safe_publish(topic, json.dumps(payload), qos=1),
            )

            # Wait for response
            try:
                return await asyncio.wait_for(future, timeout=self._request_timeout)
            except TimeoutError:
                self._pending_requests.pop(message_id, None)
                _LOGGER.warning("Topology query timeout for gateway %s", device_id)
                return None

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to query topology: %s", err)
            return None

    async def async_register_child_device(
        self,
        product_id: str,
        device_id: str,
        child_product_id: str,
        child_device_name: str,
        child_device_id: str | None = None,
    ) -> dict | None:
        """Register a child device with gateway.

        Args:
            product_id: Gateway product ID
            device_id: Gateway device ID
            child_product_id: Child device product ID
            child_device_name: Child device name (MAC/SN)
            child_device_id: Optional child device ID

        Returns:
            Dict with registration result or None if failed
        """
        if not self._connected or not self._client:
            _LOGGER.warning("MQTT not connected, cannot register child device")
            return None

        try:
            topic = f"/{product_id}/{device_id}/child/{child_device_id or child_device_name}/register"
            message_id = self._generate_message_id()

            payload = {
                "timestamp": int(time.time() * 1000),
                "messageId": message_id,
                "deviceId": child_device_id or child_device_name,
                "headers": {
                    "productId": child_product_id,
                    "deviceName": child_device_name,
                    "name": child_device_name,
                },
            }

            # Create future for response
            future = asyncio.Future()
            self._pending_requests[message_id] = future

            # Publish registration
            await self._loop.run_in_executor(
                None,
                lambda: self._safe_publish(topic, json.dumps(payload), qos=1),
            )

            # Wait for response
            try:
                return await asyncio.wait_for(future, timeout=self._request_timeout)
            except TimeoutError:
                self._pending_requests.pop(message_id, None)
                _LOGGER.warning(
                    "Child device registration timeout: %s",
                    child_device_name,
                )
                return None

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to register child device: %s", err)
            return None

    async def async_unregister_child_device(
        self,
        product_id: str,
        device_id: str,
        child_device_id: str,
    ) -> bool:
        """Unregister a child device from gateway.

        Args:
            product_id: Gateway product ID
            device_id: Gateway device ID
            child_device_id: Child device ID to unregister

        Returns:
            True if successful, False otherwise
        """
        if not self._connected or not self._client:
            _LOGGER.warning("MQTT not connected, cannot unregister child device")
            return False

        try:
            topic = f"/{product_id}/{device_id}/child/{child_device_id}/unregister"
            message_id = self._generate_message_id()

            payload = {
                "timestamp": int(time.time() * 1000),
                "messageId": message_id,
                "deviceId": child_device_id,
                "headers": {"ignore": "true"},
            }

            # Create future for response
            future = asyncio.Future()
            self._pending_requests[message_id] = future

            # Publish unregistration
            await self._loop.run_in_executor(
                None,
                lambda: self._safe_publish(topic, json.dumps(payload), qos=1),
            )

            # Wait for response
            try:
                await asyncio.wait_for(future, timeout=self._request_timeout)
            except TimeoutError:
                self._pending_requests.pop(message_id, None)
                _LOGGER.warning(
                    "Child device unregistration timeout: %s",
                    child_device_id,
                )
                return False
            else:
                return True

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to unregister child device: %s", err)
            return False

    def _safe_publish(self, topic: str, payload: str, qos: int = 1) -> None:
        """Safely publish message to MQTT broker with connection check.

        This method should be called from executor to avoid blocking.
        """
        if not self._client or not self._connected:
            raise HeimanMqttError("MQTT client not connected")

        result = self._client.publish(topic, payload, qos=qos)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise HeimanMqttError(f"Publish failed with code: {result.rc}")

    async def async_disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        self._should_reconnect = False

        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            _LOGGER.info("MQTT client disconnected")

        # Clear pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()

    @property
    def connected(self) -> bool:
        """Check if connected to MQTT broker."""
        return self._connected

    @property
    def broker(self) -> str:
        """Return the configured MQTT broker."""
        return self._broker

    @property
    def port(self) -> int:
        """Return the configured MQTT port."""
        return self._port
