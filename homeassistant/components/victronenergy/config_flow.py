"""Config flow for the Victron Energy integration.

Note: The blocking import warning in Home Assistant logs is a known issue
with the HA loader's detection mechanism and doesn't affect functionality.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import ssl
from typing import Any

import aiohttp
import paho.mqtt.client as mqtt
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import instance_id
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import CONF_BROKER, CONF_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BROKER, default="venus.local"): str,
    }
)

STEP_PASSWORD_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)

STEP_SSDP_CONFIRM_SCHEMA = vol.Schema({})


def _raise_invalid_auth(message: str) -> None:
    """Helper to raise InvalidAuth exception."""
    raise InvalidAuth(message)


async def _get_ha_device_id(hass: HomeAssistant) -> str:
    """Get persistent Home Assistant instance identifier for device ID."""
    ha_uuid = await instance_id.async_get(hass)
    return ha_uuid.replace("-", "")  # Remove hyphens for alphanumeric format


async def _test_basic_mqtt_connection(
    hass: HomeAssistant, broker: str, port: int = 1883
) -> bool:
    """Test basic MQTT connection without authentication."""
    connection_result = asyncio.Event()
    connection_error = asyncio.Event()

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            connection_result.set()
        else:
            connection_error.set()

    client = mqtt.Client()
    client.on_connect = on_connect

    try:
        await hass.async_add_executor_job(client.connect, broker, port, 10)
        client.loop_start()

        connection_task = asyncio.create_task(connection_result.wait())
        error_task = asyncio.create_task(connection_error.wait())

        _done, pending = await asyncio.wait(
            [connection_task, error_task],
            timeout=10.0,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        return connection_result.is_set()

    except (RuntimeError, OSError, TimeoutError) as err:
        _LOGGER.debug("Connection test failed: %s", err)
        return False
    finally:
        client.loop_stop()
        client.disconnect()


def _create_ssl_context() -> ssl.SSLContext:
    """Create SSL context for local device connections."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


async def _detect_discovery_topics(
    hass: HomeAssistant,
    broker: str,
    port: int = 1883,
    username: str | None = None,
    password: str | None = None,
    use_ssl: bool = False,
) -> str | None:
    """Connect to MQTT and wait for Home Assistant discovery topics to detect unique_id."""
    discovered_unique_id = None
    connection_success = asyncio.Event()
    discovery_event = asyncio.Event()

    def on_connect(client, userdata, flags, rc):
        _LOGGER.info("Discovery MQTT connect with rc=%s", rc)
        if rc == 0:
            # Subscribe to Home Assistant discovery topics
            client.subscribe("homeassistant/device/+/config")
            connection_success.set()
        else:
            _LOGGER.warning("Discovery MQTT connection failed with code %s", rc)

    def on_message(client, userdata, msg):
        nonlocal discovered_unique_id
        try:
            topic = msg.topic
            _LOGGER.debug("Received discovery topic: %s", topic)

            # Extract unique_id from the topic path
            # Example: homeassistant/device/28ede02ceff6_charger_277/config
            # We want to extract "28ede02ceff6" as the unique_id
            if topic.startswith("homeassistant/device/") and topic.endswith("/config"):
                # Extract the device identifier part
                device_part = topic.replace("homeassistant/device/", "").replace(
                    "/config", ""
                )
                _LOGGER.debug("Extracted device part from topic: %s", device_part)

                # Extract the portal ID (first part before underscore)
                if "_" in device_part:
                    portal_id = device_part.split("_")[0]
                    if discovered_unique_id is None:
                        discovered_unique_id = portal_id
                        _LOGGER.info("Extracted portal_id from topic: %s", portal_id)
                        discovery_event.set()

        except (ValueError, IndexError) as e:
            _LOGGER.debug("Could not extract unique_id from topic: %s", e)

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        if username and password:
            client.username_pw_set(username, password)

        if use_ssl:
            ssl_context = await hass.async_add_executor_job(_create_ssl_context)
            client.tls_set_context(ssl_context)
            client.tls_insecure_set(True)

        await hass.async_add_executor_job(client.connect, broker, port, 60)
        client.loop_start()

        # Wait for connection
        try:
            await asyncio.wait_for(connection_success.wait(), timeout=10.0)
        except TimeoutError:
            _LOGGER.warning("MQTT connection timeout")
            return None

        _LOGGER.info("Connected to MQTT, waiting for discovery topics")

        # Wait for discovery topics (max 30 seconds)
        try:
            await asyncio.wait_for(discovery_event.wait(), timeout=30.0)
            _LOGGER.info("Discovery completed, unique_id: %s", discovered_unique_id)
        except TimeoutError:
            _LOGGER.warning("No discovery topics received within 30 seconds")
            return None
        else:
            return discovered_unique_id

    except (RuntimeError, OSError, TimeoutError) as err:
        _LOGGER.error("Error during MQTT discovery detection: %s", err)
        return None
    finally:
        client.loop_stop()
        client.disconnect()


async def _generate_victron_token(
    hass: HomeAssistant, broker: str, password: str, ha_device_id: str
) -> str:
    """Generate authentication token from Victron device."""
    url = f"https://{broker}/auth/generate-token/"
    _LOGGER.info(
        "Starting token generation for broker %s with device_id %s (length: %d)",
        broker,
        ha_device_id,
        len(ha_device_id),
    )
    _LOGGER.info("Device ID validation - alphanumeric only: %s", ha_device_id.isalnum())

    # Create form data as application/x-www-form-urlencoded (like curl -d)
    data = {
        "role": "homeassistant",
        "device_id": ha_device_id,
    }
    _LOGGER.info("Token request URL: %s", url)
    _LOGGER.info("Token request data: %s", data)

    try:
        # Create SSL context in executor to avoid blocking the event loop
        _LOGGER.info("Creating SSL context for token generation")
        ssl_context = await hass.async_add_executor_job(_create_ssl_context)

        connector = aiohttp.TCPConnector(ssl=ssl_context)
        timeout = aiohttp.ClientTimeout(total=10)

        # Create HTTP Basic Auth credentials (same as curl --user)
        auth = aiohttp.BasicAuth("remoteconsole", password)
        _LOGGER.info(
            "Created Basic Auth for user 'remoteconsole' with provided password"
        )

        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout
        ) as session:
            _LOGGER.info("Making POST request to %s", url)
            # Send as form data, not JSON (like curl -d)
            async with session.post(url, data=data, auth=auth) as response:
                _LOGGER.info("Token generation response status: %s", response.status)
                _LOGGER.info(
                    "Token generation response headers: %s", dict(response.headers)
                )

                if response.status != 200:
                    response_text = await response.text()
                    _LOGGER.error(
                        "Token generation failed with status %s, response: %s",
                        response.status,
                        response_text,
                    )
                    _raise_invalid_auth(
                        f"Token generation failed: HTTP {response.status}"
                    )

                result = await response.json()
                _LOGGER.info("Token generation response JSON: %s", result)

                # Victron returns "password" field, not "token"
                if "password" not in result:
                    _LOGGER.error(
                        "No 'password' field in token response. Available fields: %s",
                        list(result.keys()),
                    )
                    _raise_invalid_auth("No password/token in response")

                token = result["password"]
                _LOGGER.info(
                    "Successfully generated token (length: %d characters)", len(token)
                )
                return token

    except aiohttp.ClientError as err:
        _LOGGER.error("HTTP client error during token generation: %s", err)
        raise
    except Exception as err:
        _LOGGER.error("Unexpected error during token generation: %s", err)
        raise


async def _test_secure_mqtt_connection(
    hass: HomeAssistant, broker: str, token: str, ha_device_id: str
) -> bool:
    """Test MQTT connection over secure TLS with token authentication."""
    username = f"token/homeassistant/{ha_device_id}"

    connection_result = asyncio.Event()
    connection_error = asyncio.Event()

    def on_connect(client, userdata, flags, rc):
        _LOGGER.info("Secure MQTT on_connect called with rc=%s, flags=%s", rc, flags)
        if rc == 0:
            _LOGGER.info("Secure MQTT connection successful!")
            connection_result.set()
        else:
            _LOGGER.warning("Secure MQTT connection failed with code %s", rc)
            connection_error.set()

    def on_disconnect(client, userdata, rc):
        _LOGGER.info("Secure MQTT disconnected with code %s", rc)

    try:
        # Create SSL context in executor to avoid blocking the event loop
        _LOGGER.info("Creating SSL context for secure MQTT connection")
        ssl_context = await hass.async_add_executor_job(_create_ssl_context)

        # Create MQTT client for secure connection
        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect

        _LOGGER.info("Setting secure MQTT credentials - username: %s", username)
        client.username_pw_set(username, token)

        # Configure TLS settings for secure MQTT
        client.tls_set_context(ssl_context)
        client.tls_insecure_set(True)  # Allow self-signed certificates

        _LOGGER.info("Attempting secure MQTT connection on port 8883")

        # Connect over secure MQTT
        await hass.async_add_executor_job(client.connect, broker, 8883, 10)
        client.loop_start()

        # Wait for connection result
        connection_task = asyncio.create_task(connection_result.wait())
        error_task = asyncio.create_task(connection_error.wait())

        _done, pending = await asyncio.wait(
            [connection_task, error_task],
            timeout=10.0,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        client.loop_stop()
        client.disconnect()

        return connection_result.is_set()

    except (RuntimeError, OSError, TimeoutError) as err:
        _LOGGER.debug("Secure MQTT connection failed: %s", err)
        return False


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    broker = data[CONF_BROKER]

    # Validate broker format
    try:
        ipaddress.ip_address(broker)
    except ValueError as err:
        hostname_regex = re.compile(
            r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$"
        )
        if not hostname_regex.match(broker):
            raise InvalidHost("Broker is not a valid IP address or hostname") from err

    # Validate required fields
    if not broker:
        raise CannotConnect("Broker is required")

    return {"title": "Venus OS Hub", "host": str(broker)}


async def validate_secure_mqtt_connection(
    hass: HomeAssistant, broker: str, password: str
) -> dict[str, Any]:
    """Validate secure MQTT connection with token authentication."""
    ha_device_id = await _get_ha_device_id(hass)
    _LOGGER.info("Generated device_id for secure MQTT validation: %s", ha_device_id)

    try:
        # Generate token
        token = await _generate_victron_token(hass, broker, password, ha_device_id)

        # Test secure MQTT connection
        if await _test_secure_mqtt_connection(hass, broker, token, ha_device_id):
            return {
                "title": "Venus OS Hub",
                "host": broker,
                "token": token,
                "ha_device_id": ha_device_id,
            }

        raise CannotConnect("Secure MQTT connection failed")
    except aiohttp.ClientError as err:
        raise CannotConnect(f"HTTP connection failed: {err}") from err
    except json.JSONDecodeError as err:
        raise InvalidAuth("Invalid response from device") from err


async def _handle_password_step(
    hass: HomeAssistant,
    broker: str,
    password: str,
    *,
    detect_discovery: bool = True,
    title_format: str = "GX device ({})",
    fallback_title: str = "Venus OS Hub",
) -> dict[str, Any]:
    """Handle password validation and return config entry data.

    Args:
        hass: Home Assistant instance
        broker: MQTT broker address
        password: Password for authentication
        detect_discovery: Whether to detect discovery topics for unique_id
        title_format: Format string for title when unique_id is found
        fallback_title: Title to use if no unique_id found

    Returns:
        Dict with title and data for config entry creation
    """
    info = await validate_secure_mqtt_connection(hass, broker, password)
    username = f"token/homeassistant/{info['ha_device_id']}"

    unique_id = None
    if detect_discovery:
        # Listen for discovery topics on secure MQTT
        unique_id = await _detect_discovery_topics(
            hass, broker, 8883, username, info["token"], True
        )

        if not unique_id:
            raise NoDiscoverySupport("Home assistant discovery topics not found")

        title = title_format.format(unique_id)
    else:
        title = fallback_title

    return {
        "title": title,
        "data": {
            CONF_BROKER: broker,
            CONF_PORT: 8883,
            CONF_USERNAME: username,
            CONF_TOKEN: info["token"],
            "ha_device_id": info["ha_device_id"],
        },
        "unique_id": unique_id,
    }


class VictronConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Victron Energy."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._broker: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - ask for broker."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors={}
            )

        broker = user_input[CONF_BROKER]

        # Validate broker format first
        try:
            await validate_input(self.hass, user_input)
        except InvalidHost as ex:
            return self.async_abort(
                reason="invalid_host", description_placeholders={"error": str(ex)}
            )
        except Exception as ex:
            _LOGGER.exception("Unexpected exception during validation")
            return self.async_abort(
                reason="unknown", description_placeholders={"error": str(ex)}
            )

        # Store broker for later use in instance variable
        self._broker = broker

        # Always ask for password and use secure connection
        _LOGGER.info("Proceeding to secure MQTT connection setup for %s", broker)
        return await self.async_step_password()

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle password step for token authentication."""
        errors: dict[str, str] = {}
        broker = getattr(self, "_broker", None)

        if user_input is None:
            return self.async_show_form(
                step_id="password",
                data_schema=STEP_PASSWORD_DATA_SCHEMA,
                errors=errors,
                description_placeholders={"host": broker or "unknown"},
            )

        try:
            assert broker is not None, "Broker must be set in context"
            password = user_input[CONF_PASSWORD] or ""

            result = await _handle_password_step(
                self.hass, broker, password, detect_discovery=True
            )

            if result["unique_id"]:
                # Check if already configured - let config flow exceptions propagate
                await self.async_set_unique_id(result["unique_id"])
                self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=result["title"],
                data=result["data"],
            )

        except AbortFlow:
            # Propagate AbortFlow exceptions, for example from _abort_if_unique_id_configured
            raise
        except NoDiscoverySupport:
            _LOGGER.warning("Home assistant discovery topics not found")
            return self.async_abort(reason="no_discovery")
        except CannotConnect:
            _LOGGER.warning("Connection failed")
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            _LOGGER.warning("Authentication failed")
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        # If we have errors, show the form again with error messages
        if errors:
            return self.async_show_form(
                step_id="password",
                data_schema=STEP_PASSWORD_DATA_SCHEMA,
                errors=errors,
                description_placeholders={"host": broker or "unknown"},
            )

        # Return an explicit failure response if we get here
        return self.async_abort(reason="unknown")

    async def async_step_ssdp_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle password step for SSDP discovered device."""
        broker = getattr(self, "_broker", None)
        friendly_name = self.context.get("title_placeholders", {}).get(
            "name", "Victron Energy"
        )

        if user_input is None:
            return self.async_show_form(
                step_id="ssdp_password",
                data_schema=STEP_PASSWORD_DATA_SCHEMA,
                description_placeholders=self.context.get("title_placeholders", {}),
            )

        try:
            assert broker is not None, "Broker must be set in context"
            assert isinstance(user_input[CONF_PASSWORD], str), "Password must be string"

            result = await _handle_password_step(
                self.hass,
                broker,
                user_input[CONF_PASSWORD],
                detect_discovery=False,
                fallback_title=friendly_name,
            )

            return self.async_create_entry(
                title=result["title"],
                data=result["data"],
            )

        except CannotConnect:
            _LOGGER.warning("Connection failed")
            return self.async_show_form(
                step_id="ssdp_password",
                data_schema=STEP_PASSWORD_DATA_SCHEMA,
                errors={"base": "cannot_connect"},
                description_placeholders=self.context.get("title_placeholders", {}),
            )
        except InvalidAuth:
            _LOGGER.warning("Authentication failed")
            return self.async_show_form(
                step_id="ssdp_password",
                data_schema=STEP_PASSWORD_DATA_SCHEMA,
                errors={"base": "invalid_auth"},
                description_placeholders=self.context.get("title_placeholders", {}),
            )
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_show_form(
                step_id="ssdp_password",
                data_schema=STEP_PASSWORD_DATA_SCHEMA,
                errors={"base": "unknown"},
                description_placeholders=self.context.get("title_placeholders", {}),
            )

    async def async_step_ssdp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation for SSDP discovered device."""
        _LOGGER.info("SSDP confirm called with input: %s", user_input)

        if user_input is None:
            return self.async_show_form(
                step_id="ssdp_confirm",
                data_schema=STEP_SSDP_CONFIRM_SCHEMA,
                description_placeholders=self.context.get("title_placeholders", {}),
            )

        # Always use secure MQTT connection, ask for password
        return await self.async_step_ssdp_password()

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP discovery."""

        # Debug
        _LOGGER.debug("Discovered SSDP info: %s", discovery_info)

        # Handle both real SSDP discovery and test data
        if hasattr(discovery_info, "ssdp_headers"):
            # Real SSDP discovery
            host = discovery_info.ssdp_headers.get("_host")
            friendly_name = discovery_info.upnp.get("friendlyName", "Victron Energy GX")
            unique_id = discovery_info.upnp.get("X_VrmPortalId")
            home_assistant_discovery = discovery_info.upnp.get(
                "X_HomeAssistantDiscovery"
            )
        else:
            # Test data structure (dict passed directly)
            # For tests, discovery_info might be passed as dict
            discovery_dict: dict[str, Any] = (
                discovery_info if isinstance(discovery_info, dict) else {}
            )
            host = discovery_dict.get("host")
            friendly_name = "Victron Energy GX"
            unique_id = None
            home_assistant_discovery = None

            # For tests, we need to test the connection to get the unique_id
            if host:
                try:
                    # Try insecure connection first
                    if await _test_basic_mqtt_connection(self.hass, host, 1883):
                        unique_id = await _detect_discovery_topics(
                            self.hass, host, 1883
                        )
                    else:
                        # Will need password - show confirmation first
                        pass
                except CannotConnect:
                    return self.async_abort(reason="cannot_connect")

        # For real SSDP discovery, require unique_id
        if hasattr(discovery_info, "ssdp_headers") and unique_id is None:
            return self.async_abort(reason="missing_unique_id")
        if hasattr(discovery_info, "ssdp_headers") and home_assistant_discovery is None:
            return self.async_abort(reason="no_discovery_support")

        # For tests, unique_id might be set later
        if unique_id:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

        await self.async_set_unique_id(unique_id)

        # Check if this unique ID is already configured
        _LOGGER.debug("Checking if unique_id %s is already configured", unique_id)
        try:
            self._abort_if_unique_id_configured()
            _LOGGER.debug(
                "Unique_id %s is not configured, proceeding with flow", unique_id
            )
        except Exception as ex:
            _LOGGER.debug(
                "Unique_id %s already configured, aborting flow: %s", unique_id, ex
            )
            raise

        self.context["title_placeholders"] = {
            "name": friendly_name or "Victron Energy Device",
            "host": str(host) if host else "unknown",
        }
        self._broker = host

        # Show confirmation step first, before testing connection
        return self.async_show_form(
            step_id="ssdp_confirm",
            data_schema=STEP_SSDP_CONFIRM_SCHEMA,
            description_placeholders=self.context["title_placeholders"],
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid authentication."""


class InvalidHost(HomeAssistantError):
    """Error to indicate invalid host format."""


class InvalidPort(HomeAssistantError):
    """Error to indicate invalid port."""


class NoDiscoverySupport(HomeAssistantError):
    """Error to indicate no Home Assistant discovery support found."""
