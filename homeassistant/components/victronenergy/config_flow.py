"""Config flow for the Victron Energy integration."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
from typing import Any

import paho.mqtt.client as mqtt
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import CONF_BROKER, CONF_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BROKER, default="venus.local"): str,
        vol.Required(CONF_PORT, default=1883): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    broker = data[CONF_BROKER]
    port = data[CONF_PORT]
    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)

    # Validate broker format
    try:
        ipaddress.ip_address(broker)
    except ValueError as err:
        hostname_regex = re.compile(
            r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$"
        )
        if not hostname_regex.match(broker):
            raise InvalidHost("Broker is not a valid IP address or hostname") from err

    # Validate port range
    if not isinstance(port, int) or not (0 < port < 65536):
        raise InvalidPort("Port must be an integer between 1 and 65535")

    # Validate required fields
    if not broker or not port:
        raise CannotConnect("Broker and port are required")

    # Test MQTT connection
    await _test_mqtt_connection(hass, broker, port, username, password)

    return {"title": "Venus OS Hub", "host": str(broker)}


async def _test_mqtt_connection(
    hass: HomeAssistant,
    broker: str,
    port: int,
    username: str | None,
    password: str | None,
) -> None:
    """Test MQTT connection, authentication, and discovery support."""
    connection_result = asyncio.Event()
    discovery_topics_found = asyncio.Event()
    auth_error = asyncio.Event()
    connection_error = asyncio.Event()

    discovered_topics: set[str] = set()

    def on_connect(client, userdata, flags, rc):
        """Handle MQTT connection callback."""
        if rc == 0:
            _LOGGER.debug("MQTT connection successful")
            # Subscribe to homeassistant discovery topics to check if they exist
            client.subscribe("homeassistant/#")
            connection_result.set()
        elif rc == 5:  # MQTT_ERR_AUTH
            _LOGGER.debug("MQTT authentication failed")
            auth_error.set()
        else:
            _LOGGER.debug("MQTT connection failed with code %s", rc)
            connection_error.set()

    def on_message(client, userdata, msg):
        """Handle MQTT message callback."""
        topic = msg.topic
        if topic.startswith("homeassistant/"):
            discovered_topics.add(topic)
            # We found at least one discovery topic
            if not discovery_topics_found.is_set():
                discovery_topics_found.set()

    def on_disconnect(client, userdata, rc):
        """Handle MQTT disconnect callback."""
        _LOGGER.debug("MQTT disconnected with code %s", rc)

    # Create MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # Set credentials if provided
    if username and password:
        client.username_pw_set(username, password)

    try:
        # Attempt connection in executor to avoid blocking
        await hass.async_add_executor_job(client.connect, broker, port, 10)

        # Start the client loop in background
        client.loop_start()

        # Create tasks for the wait conditions
        connection_task = asyncio.create_task(connection_result.wait())
        auth_task = asyncio.create_task(auth_error.wait())
        error_task = asyncio.create_task(connection_error.wait())

        # Wait for connection result with timeout
        try:
            done, pending = await asyncio.wait(
                (connection_task, auth_task, error_task),
                timeout=10.0,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()

        except TimeoutError:
            # Cancel all tasks on timeout
            for task in (connection_task, auth_task, error_task):
                task.cancel()
            raise CannotConnect(
                "Connection timeout - device may be unreachable"
            ) from None

        # Check what happened
        if auth_error.is_set():
            raise InvalidAuth("Invalid username or password")

        if connection_error.is_set():
            raise CannotConnect("Failed to connect to MQTT broker")

        if not connection_result.is_set():
            raise CannotConnect("Connection failed for unknown reason")

        # Wait a bit for discovery messages to arrive
        try:
            await asyncio.wait_for(discovery_topics_found.wait(), timeout=5.0)
        except TimeoutError:
            # No discovery topics found
            raise NoDiscoverySupport(
                "No Home Assistant discovery topics found - device may not support MQTT discovery"
            ) from None

        _LOGGER.debug("Found %d discovery topics", len(discovered_topics))

    except OSError as err:
        raise CannotConnect(f"Network error connecting to {broker}:{port}") from err
    finally:
        # Clean up
        client.loop_stop()
        client.disconnect()


class VictronConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Victron Energy."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidHost:
                errors["base"] = "invalid_host"
            except InvalidPort:
                errors["base"] = "invalid_port"
            except NoDiscoverySupport:
                errors["base"] = "no_discovery_support"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=str(info["title"]), data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP discovery."""

        # Debug
        _LOGGER.debug("Discovered SSDP info: %s", discovery_info)

        host = discovery_info.ssdp_headers.get("_host")
        friendly_name = discovery_info.upnp.get("friendlyName", "Victron Energy GX")
        unique_id = discovery_info.upnp.get("X_VrmPortalId")
        if unique_id is None:
            return self.async_abort(reason="missing_unique_id")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_BROKER: host,
            }
        )

        self.context["title_placeholders"] = {
            "name": friendly_name,
            "host": str(host or ""),
        }
        return self.async_show_form(
            step_id="validate",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BROKER, default=host): str,
                    vol.Required(CONF_PORT, default=1883): int,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_validate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle submission of the SSDP discovery form."""
        errors: dict[str, str] = {}
        host = self.context.get("title_placeholders", {}).get("host", "")
        if user_input is not None:
            # Merge discovered host with user input
            user_input = {**user_input, CONF_BROKER: host}
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidHost:
                errors["base"] = "invalid_host"
            except InvalidPort:
                errors["base"] = "invalid_port"
            except NoDiscoverySupport:
                errors["base"] = "no_discovery_support"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=host or "Victron Energy", data=user_input
                )

        return self.async_show_form(
            step_id="validate",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BROKER, default=host): str,
                    vol.Required(CONF_PORT, default=1883): int,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders=self.context.get("title_placeholders", {}),
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to confirm adding the device."""
        errors: dict[str, str] = {}
        host = self.context.get("title_placeholders", {}).get("host", "")
        if user_input is not None:
            # Merge discovered host with user input
            user_input = {**user_input, CONF_BROKER: host}
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidHost:
                errors["base"] = "invalid_host"
            except InvalidPort:
                errors["base"] = "invalid_port"
            except NoDiscoverySupport:
                errors["base"] = "no_discovery_support"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=host or "Victron Energy", data=user_input
                )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BROKER, default=host): str,
                    vol.Required(CONF_PORT, default=1883): int,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders=self.context.get("title_placeholders", {}),
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
