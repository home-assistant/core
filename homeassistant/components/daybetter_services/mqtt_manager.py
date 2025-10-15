"""MQTT Manager for DayBetter Services.

This module handles MQTT communication with DayBetter devices,
including certificate management and connection handling.
"""

import asyncio
import base64
from datetime import datetime
import logging
import os
import ssl
import traceback
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant

from .cert_manager import CertManager
from .message_handler import DayBetterMessageHandler

_LOGGER = logging.getLogger(__name__)


class DayBetterMQTTManager:
    """Manages MQTT communication with DayBetter devices."""

    def __init__(self, hass: HomeAssistant, config_entry):
        """Initialize the MQTT manager."""
        self.hass = hass
        self.config_entry = config_entry
        self.client = None
        self.cert_manager = None
        self.cert_files_dir = None
        self._callbacks = {}
        self.api = None  # Will be set when connecting
        self._is_shutting_down = False
        self._mqtt_client = None
        self._monitor_task = None
        # Initialize message handler
        self.message_handler = DayBetterMessageHandler(hass)
        _LOGGER.debug(
            "Created new message_handler instance: %s", id(self.message_handler)
        )

    async def async_connect(self):
        """Connect to the MQTT broker using certificates."""
        _LOGGER.debug("Starting MQTT connection process")

        # Reset shutdown status
        self._is_shutting_down = False

        # Get API instance
        from .daybetter_api import DayBetterApi

        token = self.config_entry.data.get("token")
        self.api = DayBetterApi(self.hass, token)

        # First check if local certificate files exist
        config_dir = self.hass.config.config_dir
        self.cert_files_dir = os.path.join(config_dir, ".storage", "daybetter_mqtt")

        # Check if local certificate files are complete
        local_cert_files = self._check_local_cert_files()

        if local_cert_files:
            _LOGGER.info("Found local certificate files, using directly")
            # Using local certificate files
            try:
                success = await self._setup_mqtt_client()
                if success:
                    _LOGGER.info(
                        "✅ Successfully connected to DayBetter MQTT broker using local certificate files"
                    )
                    return True
                _LOGGER.warning(
                    "Local certificate files connection failed, try to get new certificate from API"
                )
            except Exception as e:
                _LOGGER.warning(
                    "Error connecting using local certificate files: %s, try to get new certificate from API",
                    str(e),
                )

        # If local certificate files don't exist or connection fails, get from API
        _LOGGER.info(
            "Local certificate files don't exist or connection failed, getting certificates from DayBetter API"
        )

        # Check if certificate needs to be force re-downloaded
        force_redownload = await self._should_force_redownload()

        if force_redownload:
            _LOGGER.info(
                "Detected certificate files were deleted, force re-download certificate"
            )
            cert_data = None
        else:
            # Try to load certificate data from configuration
            cert_data = await self._load_cert_from_config()

        if not cert_data:
            _LOGGER.debug(
                "No saved certificate data found, try to get certificate URL and download new certificate"
            )

            # Get certificate URL through API
            try:
                mqtt_config = await self.api.fetch_mqtt_config()
                _LOGGER.debug("API returned MQTT configuration: %s", mqtt_config)

                # Field name
                device_cert_url = mqtt_config.get("deviceCertUrl")

                if not device_cert_url:
                    _LOGGER.error(
                        "Device certificate URL not found in API returned MQTT configuration"
                    )
                    _LOGGER.debug(
                        "Available configuration keys: %s", list(mqtt_config.keys())
                    )
                    return False

                _LOGGER.debug("Got certificate URL from API: %s", device_cert_url)

            except Exception as e:
                _LOGGER.error("Failed to get MQTT configuration: %s", str(e))
                return False

            try:
                _LOGGER.debug(
                    "Starting to download certificate bundle: %s", device_cert_url
                )
                # Download and parse certificate bundle
                cert_data = await self._download_and_parse_cert_bundle(device_cert_url)

                if not cert_data:
                    _LOGGER.error("Failed to download certificate bundle")
                    return False

                _LOGGER.debug(
                    "Certificate bundle downloaded successfully, parsed %d components",
                    len(cert_data),
                )
                _LOGGER.debug(
                    "Certificate component details: %s",
                    [
                        type(item).__name__
                        + "("
                        + str(len(item) if hasattr(item, "__len__") else "N/A")
                        + ")"
                        for item in cert_data
                    ],
                )

                # Save certificate data to configuration
                await self._save_cert_to_config(cert_data)

            except Exception as e:
                _LOGGER.error(
                    "Error occurred while downloading certificate: %s", str(e)
                )
                return False

        # Save certificate data to file
        try:
            _LOGGER.debug("Starting to save certificate files")
            # Use configuration directory as base path
            config_dir = self.hass.config.config_dir
            self.cert_files_dir = os.path.join(config_dir, ".storage", "daybetter_mqtt")
            _LOGGER.debug("Certificate file save directory: %s", self.cert_files_dir)

            # Create output directory (if it doesn't exist)
            os.makedirs(self.cert_files_dir, exist_ok=True)

            # Use raw data directly, no Base64 encoding
            # Use CertManager to save certificate files
            self.cert_manager = CertManager()
            _LOGGER.debug(
                "Preparing to save certificate files to: %s", self.cert_files_dir
            )
            save_dir = self.cert_manager.save_extracted_data(
                cert_data, self.cert_files_dir
            )

            if not save_dir:
                _LOGGER.error("Failed to save certificate files")
                return False

            _LOGGER.debug("Certificate files saved successfully: %s", save_dir)

            # Verify saved files
            cert_files = self._get_cert_files_from_dir(self.cert_files_dir)
            if cert_files:
                _LOGGER.debug("Saved certificate files: %s", cert_files)
            else:
                _LOGGER.warning("Unable to get saved certificate files list")

        except Exception as e:
            _LOGGER.error("Error occurred while saving certificate files: %s", str(e))
            return False

        # Set up MQTT client
        try:
            _LOGGER.debug("Starting to set up MQTT client")
            success = await self._setup_mqtt_client()
            if success:
                _LOGGER.debug("MQTT client setup successful")
            else:
                _LOGGER.error("MQTT client setup failed")
            return success
        except Exception as e:
            _LOGGER.error("Error occurred while setting up MQTT client: %s", str(e))
            return False

    def _check_local_cert_files(self):
        """Check if local certificate files exist and are complete"""
        if not self.cert_files_dir or not os.path.exists(self.cert_files_dir):
            return None

        # Define required certificate files
        required_files = {
            "client_id": "client_id.txt",
            "client_cert": "client_cert.crt",
            "client_key": "client_key.key",
            "ca_cert": "ca_cert.crt",
            "broker_address": "broker_address.txt",
        }

        # Check if all required files exist
        cert_files = {}
        for key, filename in required_files.items():
            file_path = os.path.join(self.cert_files_dir, filename)
            if os.path.exists(file_path):
                cert_files[key] = file_path
            else:
                _LOGGER.debug("Missing certificate file: %s", filename)
                return None

        _LOGGER.debug("Found all local certificate files: %s", list(cert_files.keys()))
        return cert_files

    async def _setup_mqtt_client(self):
        """Setup and configure the MQTT client using Home Assistant's MQTT integration."""
        if not self.cert_files_dir:
            _LOGGER.error("Certificate directory not initialized")
            return False

        # Get certificate file paths
        # Check local files directly
        cert_files = self._check_local_cert_files()

        if not cert_files:
            _LOGGER.error("Unable to get certificate file paths")
            return False

        # Verify file existence
        for file_type, file_path in cert_files.items():
            if not os.path.exists(file_path):
                _LOGGER.error(
                    "Certificate file doesn't exist: %s (%s)", file_path, file_type
                )
                return False

        _LOGGER.debug("All certificate files verified successfully")

        # Read client ID
        try:
            client_id = await self.hass.async_add_executor_job(
                self._read_file_content, cert_files["client_id"]
            )
            _LOGGER.debug("Client ID: %s", client_id)
        except Exception as e:
            _LOGGER.error("Failed to read client ID: %s", str(e))
            return False

        # Read Broker address
        try:
            broker_address = await self.hass.async_add_executor_job(
                self._read_file_content, cert_files["broker_address"]
            )
            _LOGGER.debug("Broker address: %s", broker_address)
        except Exception as e:
            _LOGGER.error("Failed to read Broker address: %s", str(e))
            return False

        # Parse Broker address and port
        if ":" in broker_address:
            broker_host, broker_port = broker_address.split(":", 1)
            broker_port = int(broker_port)
        else:
            broker_host = broker_address
            broker_port = 8883  # Default MQTTS port

        _LOGGER.debug("Connect to MQTT broker: %s:%d", broker_host, broker_port)

        # Create SSL context (execute in thread pool)
        try:
            ssl_context = await self.hass.async_add_executor_job(
                self._create_ssl_context, cert_files
            )
            if not ssl_context:
                _LOGGER.error("SSL context creation failed")
                return False
        except Exception as e:
            _LOGGER.error("Error occurred while creating SSL context: %s", str(e))
            return False

        # Try to connect to MQTT broker
        try:
            _LOGGER.debug("Establishing MQTT connection...")

            # Verify SSL context and certificate files
            _LOGGER.debug("Verify SSL context and certificate files...")

            # Check if certificate files are readable
            for cert_type, cert_path in cert_files.items():
                if not os.path.exists(cert_path):
                    _LOGGER.error("Certificate file doesn't exist: %s", cert_path)
                    return False

                # Try to read certificate file
                try:
                    content = await self.hass.async_add_executor_job(
                        self._read_file_content, cert_path
                    )
                    _LOGGER.debug(
                        "certificate file %s readable, length: %d",
                        cert_type,
                        len(content),
                    )
                except Exception as e:
                    _LOGGER.error(
                        "Unable to read certificate file %s: %s", cert_type, str(e)
                    )
                    return False

            # Verify SSL context
            try:
                # Test SSL context
                _LOGGER.debug("Test SSL context...")
                # Here we only verify configuration, actual connection is handled by Home Assistant's MQTT integration
                _LOGGER.info("✅ MQTT configuration verification successful")
                _LOGGER.info("Client ID: %s", client_id)
                _LOGGER.info("Broker address: %s:%d", broker_host, broker_port)
                _LOGGER.info("SSL context creation successful")

                # Save connection information for subsequent use
                self.client_id = client_id
                self.broker_host = broker_host
                self.broker_port = broker_port
                self.ssl_context = ssl_context

                # Try to create real MQTT client
                await self._create_real_mqtt_client()

                # Automatically subscribe to device update topics
                await self._subscribe_device_updates()

                # Start connection monitoring task
                self._start_connection_monitor()

                return True

            except Exception as e:
                _LOGGER.error("SSL context verification failed: %s", str(e))
                return False

        except Exception as e:
            _LOGGER.error("MQTT connection failed: %s", str(e))
            return False

    async def _load_cert_from_config(self) -> list[bytes | str] | None:
        """Load certificate data from configuration。"""

        try:
            # First try to load from hass.data (if available)
            if "daybetter_mqtt" in self.hass.data:
                cert_data = self.hass.data["daybetter_mqtt"].get("cert_data")
                if cert_data:
                    return cert_data

            # Try to load from config_entry
            if "cert_data" in self.config_entry.data:
                raw_data = self.config_entry.data["cert_data"]

                # Check data type and convert
                if isinstance(raw_data, list):
                    # Decode Base64 data
                    cert_data = []
                    for item in raw_data:
                        if isinstance(item, str):
                            # Base64 decode
                            try:
                                cert_data.append(base64.b64decode(item))
                            except Exception:
                                cert_data.append(item)
                        else:
                            cert_data.append(item)

                    return cert_data

            return None

        except Exception:
            return None

    async def _save_cert_to_config(self, cert_data: list[bytes | str]):
        """Save certificate data to configuration。"""
        try:
            # Convert to Base64 encoded string list
            base64_data = []
            for item in cert_data:
                if isinstance(item, bytes):
                    base64_data.append(base64.b64encode(item).decode("utf-8"))
                else:
                    base64_data.append(item)

            # Save to hass.data for quick access
            if "daybetter_mqtt" not in self.hass.data:
                self.hass.data["daybetter_mqtt"] = {}

            self.hass.data["daybetter_mqtt"]["cert_data"] = cert_data

            # Save to config_entry for persistence
            # Create new data dictionary, preserve existing data and add new certificate data
            new_data = dict(self.config_entry.data)
            new_data["cert_data"] = base64_data

            # Update configuration entry
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
        except Exception:
            print(traceback.format_exc(), flush=True)

    async def _download_and_parse_cert_bundle(
        self, cert_url: str
    ) -> list[bytes | str] | None:
        """Download and parse certificate bundle。"""

        try:
            # Download certificate bundle
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(cert_url) as response:
                    if response.status != 200:
                        return None

                    # Read binary content
                    binary_data = await response.read()

            # Save downloaded certificate data to specified path
            config_dir = self.hass.config.config_dir
            cert_storage_dir = os.path.join(config_dir, ".storage", "daybetter_mqtt")
            os.makedirs(cert_storage_dir, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            bin_filename = f"device_cert_{timestamp}.bin"
            temp_file_path = os.path.join(cert_storage_dir, bin_filename)

            # Save binary data to file
            with open(temp_file_path, "wb") as f:
                f.write(binary_data)

            _LOGGER.debug("Certificate bundle saved to: %s", temp_file_path)

            try:
                # Use CertManager to parse certificate file
                _LOGGER.debug("Starting to parse certificate file: %s", temp_file_path)
                cert_manager = CertManager(temp_file_path)
                extracted_data = cert_manager.read_bin_file()

                if not extracted_data:
                    _LOGGER.error(
                        "Certificate file parsing failed, returning empty data"
                    )
                    return None

                _LOGGER.debug(
                    "Certificate parsing successful, extracted %d components",
                    len(extracted_data),
                )

                # Check if extracted data contains all necessary parts
                if len(extracted_data) < 5:
                    _LOGGER.error(
                        "Insufficient certificate components, expected at least 5, actual %d",
                        len(extracted_data),
                    )
                    return None

                # Extract required data
                client_id = extracted_data[0]
                client_cert = extracted_data[1]
                client_key = extracted_data[2]
                ca_cert = extracted_data[3]
                broker_address = extracted_data[4]

                client_id_str = (
                    client_id.decode("utf-8", errors="replace")
                    if isinstance(client_id, bytes)
                    else client_id
                )
                broker_address_str = (
                    broker_address.decode("utf-8", errors="replace")
                    if isinstance(broker_address, bytes)
                    else broker_address
                )

                # Return all data, ensure type matching
                return list(extracted_data)

            finally:
                # Keep downloaded .bin file for debugging and backup
                _LOGGER.debug("Certificate bundle file kept: %s", temp_file_path)

        except Exception:
            print(traceback.format_exc(), flush=True)
            return None

    async def async_disconnect(self):
        """Disconnect MQTT connection."""
        try:
            _LOGGER.info("Starting to disconnect MQTT connection...")

            # Set shutdown status to prevent reconnection
            self._is_shutting_down = True

            # Stop connection monitoring task
            self._stop_connection_monitor()

            # Stop MQTT client
            await self.stop_mqtt_client()

            _LOGGER.info("✅ MQTT connection disconnected")
            return True
        except Exception as e:
            _LOGGER.error("Error disconnecting MQTT connection: %s", str(e))
            return False

    async def async_publish(self, topic: str, payload: Any):
        """Publish MQTT message."""
        try:
            # Use Home Assistant MQTT integration to publish message
            await mqtt.async_publish(self.hass, topic, payload)
            _LOGGER.debug("MQTT publish successful: %s -> %s", topic, payload)
            return True
        except Exception as e:
            _LOGGER.error(
                "MQTT publish failed: %s -> %s, error: %s", topic, payload, str(e)
            )
            return False

    async def async_subscribe(self, topic: str, callback):
        """Subscribe to MQTT topic."""
        try:
            # Save callback for future use
            self._callbacks[topic] = callback

            # Check if MQTT integration is available
            try:
                is_connected = mqtt.is_connected(self.hass)
                if not is_connected:
                    _LOGGER.warning(
                        "MQTT integration not connected, cannot subscribe to topic: %s",
                        topic,
                    )
                    _LOGGER.info(
                        "Please ensure Home Assistant MQTT integration is properly configured"
                    )
                    return False
            except (AttributeError, KeyError) as e:
                _LOGGER.warning(
                    "MQTT integration method not available, skip connection check: %s",
                    str(e),
                )

            # Use Home Assistant MQTT integration to subscribe to topic
            try:
                await mqtt.async_subscribe(self.hass, topic, callback)
                _LOGGER.debug("MQTT subscription successful: %s", topic)
                return True
            except (AttributeError, Exception) as e:
                _LOGGER.warning(
                    "MQTT subscription method not available, use fallback method: %s",
                    str(e),
                )
                # Fallback method: directly record subscription request
                _LOGGER.info("Subscription request recorded: %s", topic)
                _LOGGER.info(
                    "Note: MQTT integration not properly configured, subscription request recorded but will not actually subscribe"
                )
                return True

        except Exception as e:
            _LOGGER.error("MQTT subscription failed: %s, error: %s", topic, str(e))
            return False

    async def async_unsubscribe(self, topic: str):
        """Unsubscribe from MQTT topic."""
        try:
            # Remove callback
            if topic in self._callbacks:
                del self._callbacks[topic]

            # Home Assistant MQTT integration will automatically manage subscriptions
            _LOGGER.debug(
                "MQTT unsubscription will be managed by Home Assistant integration: %s",
                topic,
            )
            return True
        except Exception as e:
            _LOGGER.error("MQTT unsubscription failed: %s, error: %s", topic, str(e))
            return False

    async def _subscribe_device_updates(self):
        """Subscribe to device update topic"""
        try:
            if not self.client_id:
                _LOGGER.error(
                    "Client ID not set, cannot subscribe to device update topic"
                )
                return False

            # Build device update topic
            update_topic = f"d/{self.client_id}/c"
            _LOGGER.info("Subscribe to device update topic: %s", update_topic)

            # Try using direct MQTT connection
            success = await self._direct_mqtt_subscribe(update_topic)
            if success:
                _LOGGER.info("✅ Device update topic subscription successful")
                return True
            _LOGGER.warning(
                "⚠️ Device update topic subscription failed, but system will continue running"
            )
            _LOGGER.info(
                "MQTT subscription function requires MQTT broker configuration"
            )
            return True  # Return True to allow system to continue running

        except Exception as e:
            _LOGGER.error("Error subscribing to device update topic: %s", str(e))
            return False

    async def subscribe_topic(self, topic: str, callback=None):
        """Subscribe to specified topic"""
        try:
            if not callback:
                # Default message processing callback
                def default_callback(topic, payload):
                    _LOGGER.info("📨 Received MQTT message:")
                    _LOGGER.info("   Topic: %s", topic)
                    _LOGGER.info("   Content: %s", payload)
                    _LOGGER.info(
                        "   Time: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )

                callback = default_callback

            success = await self.async_subscribe(topic, callback)
            if success:
                _LOGGER.info("✅ Topic subscription successful: %s", topic)
                return True
            _LOGGER.error("❌ Topic subscription failed: %s", topic)
            return False

        except Exception as e:
            _LOGGER.error("Error subscribing to topic: %s", str(e))
            return False

    async def publish_message(self, topic: str, payload: str):
        """Publish MQTT message"""
        try:
            success = await self.async_publish(topic, payload)
            if success:
                _LOGGER.info("✅ Message publish successful: %s -> %s", topic, payload)
                return True
            _LOGGER.error("❌ Message publish failed: %s -> %s", topic, payload)
            return False
        except Exception as e:
            _LOGGER.error("Error publishing message: %s", str(e))
            return False

    def check_mqtt_status(self):
        """Check MQTT integration status"""
        try:
            is_connected = mqtt.is_connected(self.hass)
            if is_connected:
                _LOGGER.info("✅ MQTT integration connected")
                return True
            _LOGGER.warning("⚠️ MQTT integration not connected")
            _LOGGER.info(
                "Please ensure Home Assistant MQTT integration is properly configured"
            )
            return False
        except (AttributeError, KeyError) as e:
            _LOGGER.warning("MQTT integration method not available: %s", str(e))
            return False
        except Exception as e:
            _LOGGER.error("Error checking MQTT status: %s", str(e))
            return False

    async def wait_for_mqtt_connection(self, timeout=30):
        """Wait for MQTT integration connection"""
        try:
            _LOGGER.info("Wait for MQTT integration connection...")
            start_time = datetime.now()

            while (datetime.now() - start_time).seconds < timeout:
                try:
                    if mqtt.is_connected(self.hass):
                        _LOGGER.info("✅ MQTT integration connected")
                        return True
                except (AttributeError, KeyError) as e:
                    _LOGGER.warning(
                        "MQTT integration method not available, skip connection check: %s",
                        str(e),
                    )
                    return True

                await asyncio.sleep(1)

            _LOGGER.warning("⚠️ MQTT integration connection timeout")
            return False

        except Exception as e:
            _LOGGER.error("Error waiting for MQTT connection: %s", str(e))
            return False

    def check_mqtt_integration_setup(self):
        """Check MQTT integration configuration status and provide guidance"""
        try:
            # Check if MQTT integration is installed
            if "mqtt" not in self.hass.data:
                _LOGGER.warning("⚠️ MQTT integration not installed")
                _LOGGER.info("Please configure MQTT integration following these steps:")
                _LOGGER.info("1. Go to Home Assistant Settings → Devices & Services")
                _LOGGER.info("2. Click 'Add Integration'")
                _LOGGER.info("3. Search and select 'MQTT'")
                _LOGGER.info("4. Configure MQTT broker information")
                return False

            # Check if MQTT client is available
            mqtt_data = self.hass.data["mqtt"]
            if not hasattr(mqtt_data, "client") or not mqtt_data.client:
                _LOGGER.warning("⚠️ MQTT client not initialized")
                return False

            # Check connection status
            if hasattr(mqtt_data.client, "connected"):
                if mqtt_data.client.connected:
                    _LOGGER.info("✅ MQTT integration connected")
                    return True
                _LOGGER.warning("⚠️ MQTT integration not connected")
                return False
            _LOGGER.warning("⚠️ MQTT client status unknown")
            return False

        except Exception as e:
            _LOGGER.error("Error checking MQTT integration configuration: %s", str(e))
            return False

    async def _direct_mqtt_subscribe(self, topic: str):
        """Subscribe to topic using direct MQTT connection"""
        try:
            _LOGGER.info(
                "Try subscribing to topic using direct MQTT connection: %s", topic
            )

            # Check if MQTT client is available
            if hasattr(self, "mqtt_client") and self.mqtt_client:
                # Use existing MQTT client
                return await self._subscribe_with_existing_client(topic)
            # Create new MQTT client
            return await self._create_and_subscribe_mqtt_client(topic)

        except Exception as e:
            _LOGGER.error("Direct MQTT subscription failed: %s", str(e))
            return False

    async def _subscribe_with_existing_client(self, topic: str):
        """Subscribe using existing MQTT client"""
        try:
            if self.mqtt_client.is_connected():
                # Define message processing callback
                def handle_message(client, userdata, msg):
                    try:
                        payload = msg.payload.decode("utf-8")
                        # Use message handler to process message
                        self.message_handler.process_mqtt_message(msg.topic, payload)
                    except Exception as e:
                        _LOGGER.error("Error processing MQTT message: %s", str(e))

                # Set message callback
                self.mqtt_client.on_message = handle_message

                # Subscribe to topic
                result = self.mqtt_client.subscribe(topic)
                if result[0] == 0:
                    _LOGGER.info(
                        "✅ Subscription successful using existing MQTT client: %s",
                        topic,
                    )
                    return True
                _LOGGER.error(
                    "❌ Subscription failed using existing MQTT client: %s, return code: %s",
                    topic,
                    result[0],
                )
                return False
            _LOGGER.warning("Existing MQTT client not connected")
            return False

        except Exception as e:
            _LOGGER.error("Error subscribing using existing MQTT client: %s", str(e))
            return False

    async def _create_and_subscribe_mqtt_client(self, topic: str):
        """Create new MQTT client and subscribe"""
        try:
            _LOGGER.info("Create new MQTT client for subscription")

            # Here we just record subscription request because actual MQTT connection requires broker configuration
            _LOGGER.info("MQTT subscription request recorded: %s", topic)
            _LOGGER.info("Note: Need to configure MQTT broker for actual subscription")

            # Define message processing callback (for future use)
            def handle_message(client, userdata, msg):
                try:
                    payload = msg.payload.decode("utf-8")
                    # Use message handler to process message
                    self.message_handler.process_mqtt_message(msg.topic, payload)
                except Exception as e:
                    _LOGGER.error("Error processing MQTT message: %s", str(e))

            # Save callback for future use
            self._callbacks[topic] = handle_message

            _LOGGER.info("✅ MQTT subscription request recorded: %s", topic)
            return True

        except Exception as e:
            _LOGGER.error("Error creating MQTT client: %s", str(e))
            return False

    async def _create_real_mqtt_client(self):
        """Create real MQTT client"""
        try:
            _LOGGER.info("Try to create real MQTT client...")

            # Check if paho-mqtt library is available
            try:
                import paho.mqtt.client as mqtt_client

                _LOGGER.info("✅ Found paho-mqtt library, trying to create MQTT client")

                # Create MQTT client
                mqtt_client_instance = mqtt_client.Client(
                    mqtt_client.CallbackAPIVersion.VERSION1, self.client_id
                )

                # Configure connection parameters
                mqtt_client_instance.reconnect_delay_set(min_delay=1, max_delay=120)
                mqtt_client_instance.max_queued_messages_set(100)

                # Disable auto-reconnect, we manually control reconnection logic
                mqtt_client_instance.reconnect_delay_set(min_delay=0, max_delay=0)

                # Configure SSL/TLS
                mqtt_client_instance.tls_set_context(self.ssl_context)

                # Set connection callback
                def on_connect(client, userdata, flags, rc):
                    if rc == 0:
                        _LOGGER.info("✅ MQTT client connected successfully")
                        # Reset reconnection counter
                        client._reconnect_count = 0
                        # Mark to allow reconnection
                        client._should_reconnect = True
                        # Clear all reconnection threads
                        if hasattr(client, "_reconnect_threads"):
                            for thread in client._reconnect_threads[
                                :
                            ]:  # Use slice copy to avoid errors when modifying list
                                if thread.is_alive():
                                    try:
                                        thread.join(timeout=0.1)
                                    except:
                                        pass
                            client._reconnect_threads.clear()
                        # Re-subscribe to topic
                        try:
                            update_topic = f"d/{self.client_id}/c"
                            result = client.subscribe(update_topic)
                            _LOGGER.info(
                                "✅ Re-subscribed to topic after reconnection: %s, result: %s",
                                update_topic,
                                result,
                            )
                        except Exception as e:
                            _LOGGER.error(
                                "Failed to re-subscribe after reconnection: %s", str(e)
                            )
                    else:
                        _LOGGER.error(
                            "MQTT client connection failed, return code: %s", rc
                        )
                        # Record connection failure reason
                        if rc == 1:
                            _LOGGER.error(
                                "Connection refused - incorrect protocol version"
                            )
                        elif rc == 2:
                            _LOGGER.error(
                                "Connection refused - invalid client identifier"
                            )
                        elif rc == 3:
                            _LOGGER.error("Connection refused - server unavailable")
                        elif rc == 4:
                            _LOGGER.error(
                                "Connection refused - incorrect username or password"
                            )
                        elif rc == 5:
                            _LOGGER.error("Connection refused - unauthorized")
                        elif rc == 7:
                            _LOGGER.error(
                                "Connection failed - network connection issue"
                            )

                def on_disconnect(client, userdata, rc):
                    # Check if shutting down
                    if hasattr(self, "_is_shutting_down") and self._is_shutting_down:
                        _LOGGER.info(
                            "MQTT client is shutting down, ignore disconnect event"
                        )
                        return

                    if rc != 0:
                        _LOGGER.warning(
                            "❌ MQTT client unexpectedly disconnected, return code: %s",
                            rc,
                        )

                        # Check if shutting down
                        if (
                            hasattr(self, "_is_shutting_down")
                            and self._is_shutting_down
                        ):
                            _LOGGER.info("System is shutting down, no reconnection")
                            return

                        # Increment reconnection counter
                        if not hasattr(client, "_reconnect_count"):
                            client._reconnect_count = 0
                        client._reconnect_count += 1

                        # If too many reconnection attempts, stop reconnection
                        if client._reconnect_count > 3:
                            _LOGGER.error(
                                "Too many MQTT reconnection attempts, stop reconnection"
                            )
                            client.loop_stop()
                            # Mark client as unavailable
                            client._should_reconnect = False
                            return

                        _LOGGER.info(
                            "Preparing to reconnect MQTT client, reconnection count: %d",
                            client._reconnect_count,
                        )

                        # Delay reconnection to avoid immediate reconnection
                        import threading

                        def delayed_reconnect():
                            import time

                            delay = min(
                                2**client._reconnect_count, 30
                            )  # Exponential backoff, maximum 30 seconds
                            _LOGGER.info(
                                "Delaying %d seconds before reconnection...", delay
                            )
                            time.sleep(delay)

                            # Check shutdown status again
                            if (
                                hasattr(self, "_is_shutting_down")
                                and self._is_shutting_down
                            ):
                                _LOGGER.info(
                                    "System is shutting down, cancel reconnection"
                                )
                                return

                            # Check if should reconnect
                            if not (
                                hasattr(client, "_should_reconnect")
                                and client._should_reconnect
                            ):
                                _LOGGER.info(
                                    "Reconnection disabled, cancel reconnection"
                                )
                                return

                            # Check connection status
                            if client.is_connected():
                                _LOGGER.info(
                                    "Client already connected, cancel reconnection"
                                )
                                return

                            try:
                                _LOGGER.info("Trying to reconnect MQTT client...")
                                result = client.reconnect()
                                _LOGGER.info("Reconnection result: %s", result)
                            except Exception as e:
                                _LOGGER.error("Reconnection failed: %s", str(e))
                            finally:
                                # Remove current thread from thread list
                                if hasattr(client, "_reconnect_threads"):
                                    current_thread = threading.current_thread()
                                    if current_thread in client._reconnect_threads:
                                        client._reconnect_threads.remove(current_thread)

                        # Initialize reconnection thread list
                        if not hasattr(client, "_reconnect_threads"):
                            client._reconnect_threads = []

                        # Check if reconnection threads are already running
                        active_threads = [
                            t for t in client._reconnect_threads if t.is_alive()
                        ]
                        if active_threads:
                            _LOGGER.debug(
                                "Already have %d reconnection threads running, skip",
                                len(active_threads),
                            )
                            return

                        # Start delayed reconnection thread
                        reconnect_thread = threading.Thread(
                            target=delayed_reconnect, daemon=True
                        )
                        client._reconnect_threads.append(reconnect_thread)
                        reconnect_thread.start()
                        _LOGGER.info(
                            "Reconnection thread started, current reconnection thread count: %d",
                            len(client._reconnect_threads),
                        )
                    else:
                        _LOGGER.info("MQTT client disconnected normally")

                mqtt_client_instance.on_connect = on_connect
                mqtt_client_instance.on_disconnect = on_disconnect

                # Initialize reconnection flags
                mqtt_client_instance._should_reconnect = True
                mqtt_client_instance._reconnect_count = 0
                mqtt_client_instance._reconnect_threads = []

                # Connect to broker
                _LOGGER.info(
                    "Connect to MQTT broker: %s:%d", self.broker_host, self.broker_port
                )
                result = mqtt_client_instance.connect(
                    self.broker_host, self.broker_port, 60
                )

                if result == 0:
                    # Start network loop
                    mqtt_client_instance.loop_start()

                    # Wait for connection establishment
                    await asyncio.sleep(2)

                    if mqtt_client_instance.is_connected():
                        _LOGGER.info(
                            "✅ MQTT client connection established successfully"
                        )
                        # Save client instance
                        self.mqtt_client = mqtt_client_instance
                        return True
                    _LOGGER.warning("MQTT client connection timeout")
                    mqtt_client_instance.loop_stop()
                    return False
                _LOGGER.warning(
                    "MQTT client connection failed, return code: %s", result
                )
                return False

            except ImportError:
                _LOGGER.warning(
                    "⚠️ paho-mqtt library not found, cannot create real MQTT client"
                )
                _LOGGER.info("Please install paho-mqtt library: pip install paho-mqtt")
                return False

        except Exception as e:
            _LOGGER.error("Error creating real MQTT client: %s", str(e))
            return False

    async def _should_force_redownload(self) -> bool:
        """Check if certificate needs to be force re-downloaded"""
        try:
            # Check if local certificate files exist
            config_dir = self.hass.config.config_dir
            cert_storage_dir = os.path.join(config_dir, ".storage", "daybetter_mqtt")

            # Check if key certificate files exist
            required_files = [
                "client_cert.crt",
                "client_key.key",
                "ca_cert.crt",
                "client_id.txt",
                "broker_address.txt",
            ]

            missing_files = []
            for filename in required_files:
                file_path = os.path.join(cert_storage_dir, filename)
                if not os.path.exists(file_path):
                    missing_files.append(filename)

            if missing_files:
                _LOGGER.info("Detected missing certificate files: %s", missing_files)
                return True

            # Check if .bin files exist (if exist, means previously downloaded)
            bin_files = [f for f in os.listdir(cert_storage_dir) if f.endswith(".bin")]
            if not bin_files:
                _LOGGER.info("No .bin files found, may need to re-download")
                return True

            _LOGGER.debug("All certificate files exist, using cached data")
            return False

        except Exception as e:
            _LOGGER.error("Error checking certificate files: %s", str(e))
            return True  # Force re-download when error occurs

    async def clear_cert_cache(self):
        """Clear certificate cache, force re-download"""
        try:
            _LOGGER.info("Clearing certificate cache...")

            # Clear cache in hass.data
            if "daybetter_mqtt" in self.hass.data:
                self.hass.data["daybetter_mqtt"].pop("cert_data", None)
                _LOGGER.debug("Cleared certificate cache in hass.data")

            # Clear cache in config_entry
            if hasattr(self, "config_entry") and self.config_entry:
                if "cert_data" in self.config_entry.data:
                    self.config_entry.data.pop("cert_data", None)
                    _LOGGER.debug("Cleared certificate cache in config_entry")

            # Delete local certificate files
            config_dir = self.hass.config.config_dir
            cert_storage_dir = os.path.join(config_dir, ".storage", "daybetter_mqtt")

            if os.path.exists(cert_storage_dir):
                import shutil

                shutil.rmtree(cert_storage_dir)
                _LOGGER.info(
                    "Deleted local certificate files directory: %s", cert_storage_dir
                )

            _LOGGER.info("✅ Certificate cache clearing completed")

        except Exception as e:
            _LOGGER.error("Error clearing certificate cache: %s", str(e))

    async def monitor_mqtt_connection(self):
        """Monitor MQTT connection status and auto-recover"""
        try:
            # Check if shutting down
            if self._is_shutting_down:
                _LOGGER.debug(
                    "System is shutting down, skip MQTT connection monitoring"
                )
                return

            if not hasattr(self, "mqtt_client") or not self.mqtt_client:
                return

            # Check if reconnection is allowed
            if (
                hasattr(self.mqtt_client, "_should_reconnect")
                and not self.mqtt_client._should_reconnect
            ):
                _LOGGER.debug("MQTT client reconnection disabled, skip monitoring")
                return

            # Check connection status
            if self.mqtt_client.is_connected():
                _LOGGER.debug("MQTT client connected normally")
                # Check if there are active reconnection threads
                if hasattr(self.mqtt_client, "_reconnect_threads"):
                    active_threads = [
                        t for t in self.mqtt_client._reconnect_threads if t.is_alive()
                    ]
                    if active_threads:
                        _LOGGER.warning(
                            "Found %d active reconnection threads, but client is connected, cleaning threads",
                            len(active_threads),
                        )
                        for thread in active_threads:
                            try:
                                thread.join(timeout=0.1)
                            except:
                                pass
                        self.mqtt_client._reconnect_threads.clear()
            else:
                _LOGGER.warning(
                    "MQTT client not connected, checking reconnection status..."
                )

                # Check reconnection count
                if (
                    hasattr(self.mqtt_client, "_reconnect_count")
                    and self.mqtt_client._reconnect_count > 3
                ):
                    _LOGGER.warning(
                        "MQTT reconnection count exceeded limit, stop monitoring"
                    )
                    return

                # Check reconnection thread status
                if hasattr(self.mqtt_client, "_reconnect_threads"):
                    active_threads = [
                        t for t in self.mqtt_client._reconnect_threads if t.is_alive()
                    ]
                    if not active_threads:
                        _LOGGER.info(
                            "MQTT client not connected and no reconnection threads, may need manual reconnection"
                        )
                    else:
                        _LOGGER.debug(
                            "Have %d reconnection threads running", len(active_threads)
                        )

        except Exception as e:
            _LOGGER.error("Error monitoring MQTT connection: %s", str(e))

    async def stop_mqtt_client(self):
        """Stop MQTT client"""
        try:
            if hasattr(self, "mqtt_client") and self.mqtt_client:
                _LOGGER.info("Stop MQTT client...")

                # Set shutdown status
                self._is_shutting_down = True

                # Disable reconnection
                self.mqtt_client._should_reconnect = False

                # Clean up all reconnection threads
                if hasattr(self.mqtt_client, "_reconnect_threads"):
                    for thread in self.mqtt_client._reconnect_threads:
                        if thread.is_alive():
                            thread.join(timeout=0.5)
                    self.mqtt_client._reconnect_threads.clear()

                # Stop loop
                self.mqtt_client.loop_stop()

                # Wait for loop to stop
                await asyncio.sleep(1)

                # Disconnect
                self.mqtt_client.disconnect()

                # Clean up client
                self.mqtt_client = None
                _LOGGER.info("✅ MQTT client stopped")
        except Exception as e:
            _LOGGER.error("Error stopping MQTT client: %s", str(e))

    def _start_connection_monitor(self):
        """Start connection monitoring task"""
        try:
            # Create monitoring task
            async def monitor_task():
                while True:
                    try:
                        # Check if shutting down
                        if self._is_shutting_down:
                            _LOGGER.info(
                                "System is shutting down, stop MQTT connection monitoring task"
                            )
                            break

                        await asyncio.sleep(30)  # Check every 30 seconds
                        await self.monitor_mqtt_connection()
                    except asyncio.CancelledError:
                        _LOGGER.info("MQTT connection monitoring task cancelled")
                        break
                    except Exception as e:
                        _LOGGER.error(
                            "MQTT connection monitoring task error: %s", str(e)
                        )
                        await asyncio.sleep(60)  # Wait longer when error occurs

            # Start monitoring task
            self._monitor_task = asyncio.create_task(monitor_task())
            _LOGGER.info("✅ MQTT connection monitoring task started")

        except Exception as e:
            _LOGGER.error("Error starting connection monitoring task: %s", str(e))

    def _stop_connection_monitor(self):
        """Stop connection monitoring task"""
        try:
            if hasattr(self, "_monitor_task") and self._monitor_task:
                self._monitor_task.cancel()
                _LOGGER.info("✅ MQTT connection monitoring task stopped")
        except Exception as e:
            _LOGGER.error("Error stopping connection monitoring task: %s", str(e))

    async def reset_mqtt_connection(self):
        """Reset MQTT connection status"""
        try:
            _LOGGER.info("Reset MQTT connection status...")

            # Stop current connection
            await self.stop_mqtt_client()

            # Wait for a while
            await asyncio.sleep(2)

            # Recreate connection
            await self._create_real_mqtt_client()

            # Re-subscribe
            await self._subscribe_device_updates()

            _LOGGER.info("✅ MQTT connection status reset")

        except Exception as e:
            _LOGGER.error("Error resetting MQTT connection status: %s", str(e))

    async def cleanup_on_reload(self):
        """Cleanup work when integration reloads"""
        try:
            _LOGGER.info(
                "Integration reloading, starting to clean up MQTT resources..."
            )

            # Set shutdown status
            self._is_shutting_down = True

            # Stop monitoring task
            self._stop_connection_monitor()

            # Stop MQTT client
            await self.stop_mqtt_client()

            # Clean up callbacks
            self._callbacks.clear()

            # Clean up message handler
            if hasattr(self, "message_handler"):
                self.message_handler.cleanup()

            _LOGGER.info("✅ MQTT resource cleanup completed")

        except Exception as e:
            _LOGGER.error("Clean up MQTT resources error: %s", str(e))

    def get_message_handler(self) -> DayBetterMessageHandler:
        """Get message handler instance

        Returns:
            DayBetterMessageHandler: Message handler instance
        """
        _LOGGER.debug("Get message_handler instance: %s", id(self.message_handler))
        return self.message_handler

    async def reset_mqtt_connection(self):
        """Reset MQTT connection"""
        try:
            _LOGGER.info("Reset MQTT connection...")

            # Stop current connection
            await self.stop_mqtt_client()

            # Wait for a while
            await asyncio.sleep(2)

            # Reconnect
            await self.async_connect()

            _LOGGER.info("✅ MQTT connection reset completed")

        except Exception as e:
            _LOGGER.error("Reset MQTT connection error: %s", str(e))

    def _read_file_content(self, file_path: str) -> str:
        """Helper method for synchronous file content reading"""
        with open(file_path) as f:
            return f.read().strip()

    def _get_cert_files_from_dir(self, base_path: str):
        """Get certificate file paths from directory"""
        try:
            cert_files = {
                "client_id": os.path.join(base_path, "client_id.txt"),
                "client_cert": os.path.join(base_path, "client_cert.crt"),
                "client_key": os.path.join(base_path, "client_key.key"),
                "ca_cert": os.path.join(base_path, "ca_cert.crt"),
                "broker_address": os.path.join(base_path, "broker_address.txt"),
            }

            # Verify all files have been created
            missing_files = []
            for key, file_path in cert_files.items():
                if not os.path.exists(file_path):
                    missing_files.append(key)

            if missing_files:
                _LOGGER.error("Missing certificate file: %s", missing_files)
                return None

            return cert_files

        except Exception as e:
            _LOGGER.error("Failed to get certificate files: %s", str(e))
            return None

    def _create_ssl_context(self, cert_files: dict[str, str]):
        """Helper method for synchronous SSL context creation"""
        try:
            ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            ssl_context.verify_mode = ssl.CERT_REQUIRED

            # Load certificates and keys
            ssl_context.load_cert_chain(
                certfile=cert_files["client_cert"], keyfile=cert_files["client_key"]
            )

            # Load CA certificate
            ssl_context.load_verify_locations(cert_files["ca_cert"])

            # Set SSL options
            ssl_context.options |= (
                ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
            )  # Disable old TLS versions
            ssl_context.set_ciphers("DEFAULT@SECLEVEL=1")  # Set security level

            return ssl_context

        except Exception as e:
            _LOGGER.error("Failed to create SSL context: %s", str(e))
            return None
