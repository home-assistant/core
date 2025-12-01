"""Config flow for the Victron Energy integration."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import ssl
import uuid
from typing import Any

import aiohttp
import paho.mqtt.client as mqtt
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import CONF_BROKER, CONF_PORT, DOMAIN


_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Victron Energy config flow module loaded - this should appear in logs")

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BROKER, default="venus.local"): str,
    }
)

STEP_PASSWORD_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_SSDP_CONFIRM_SCHEMA = vol.Schema({})

STEP_SSDP_PASSWORD_MENU_SCHEMA = vol.Schema({
    vol.Required("next_step", default="retry"): vol.In({
        "retry": "Try again",
        "cancel": "Cancel setup"
    })
})


def _generate_ha_device_id() -> str:
    """Generate a unique Home Assistant device identifier."""
    # Generate UUID and remove hyphens to make it alphanumeric only
    device_id = str(uuid.uuid4()).replace("-", "")
    return device_id


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

        done, pending = await asyncio.wait(
            [connection_task, error_task],
            timeout=10.0,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        return connection_result.is_set()

    except Exception:
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

async def _generate_victron_token(
    hass: HomeAssistant, broker: str, password: str, ha_device_id: str
) -> str:
    """Generate authentication token from Victron device."""
    url = f"https://{broker}/auth/generate-token/"
    _LOGGER.info("Starting token generation for broker %s with device_id %s (length: %d)", broker, ha_device_id, len(ha_device_id))
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
        _LOGGER.info("Created Basic Auth for user 'remoteconsole' with provided password")

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            _LOGGER.info("Making POST request to %s", url)
            # Send as form data, not JSON (like curl -d)
            async with session.post(url, data=data, auth=auth) as response:
                _LOGGER.info("Token generation response status: %s", response.status)
                _LOGGER.info("Token generation response headers: %s", dict(response.headers))

                if response.status != 200:
                    response_text = await response.text()
                    _LOGGER.error("Token generation failed with status %s, response: %s", response.status, response_text)
                    raise InvalidAuth(f"Token generation failed: HTTP {response.status}")

                result = await response.json()
                _LOGGER.info("Token generation response JSON: %s", result)

                # Victron returns "password" field, not "token"
                if "password" not in result:
                    _LOGGER.error("No 'password' field in token response. Available fields: %s", list(result.keys()))
                    raise InvalidAuth("No password/token in response")

                token = result["password"]
                _LOGGER.info("Successfully generated token (length: %d characters)", len(token))
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
        await hass.async_add_executor_job(
            client.connect, broker, 8883, 10
        )
        client.loop_start()

        # Wait for connection result
        connection_task = asyncio.create_task(connection_result.wait())
        error_task = asyncio.create_task(connection_error.wait())

        done, pending = await asyncio.wait(
            [connection_task, error_task],
            timeout=10.0,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        client.loop_stop()
        client.disconnect()

        return connection_result.is_set()

    except Exception as err:
        _LOGGER.info("Secure MQTT connection failed: %s", err)
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
    ha_device_id = _generate_ha_device_id()
    _LOGGER.info("Generated device_id for secure MQTT validation: %s", ha_device_id)

    try:
        # Generate token
        token = await _generate_victron_token(hass, broker, password, ha_device_id)

        # Test secure MQTT connection
        if not await _test_secure_mqtt_connection(hass, broker, token, ha_device_id):
            raise CannotConnect("Secure MQTT connection failed")

        return {
            "title": "Venus OS Hub",
            "host": broker,
            "token": token,
            "ha_device_id": ha_device_id,
        }

    except aiohttp.ClientError as err:
        raise CannotConnect(f"HTTP connection failed: {err}") from err
    except json.JSONDecodeError as err:
        raise InvalidAuth("Invalid response from device") from err



class VictronConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Victron Energy."""

    VERSION = 1
    
    def __init__(self):
        """Initialize the config flow."""
        super().__init__()
        _LOGGER.info("VictronConfigFlow.__init__ called - config flow instance created")
    
    def _log_existing_entries(self, context: str = "") -> list:
        """Log all existing entries for this domain and return problematic ones."""
        all_entries = self.hass.config_entries.async_entries()
        victron_entries = [e for e in all_entries if e.domain == DOMAIN]
        
        _LOGGER.info("%s: Found %d total entries for domain '%s'", context, len(victron_entries), DOMAIN)
        
        problematic_entries = []
        for entry in victron_entries:
            _LOGGER.info("  Entry %s:", entry.entry_id)
            _LOGGER.info("    Title: %s", entry.title)
            _LOGGER.info("    Broker: %s", entry.data.get(CONF_BROKER))
            _LOGGER.info("    State: %s", entry.state)
            _LOGGER.info("    Unique ID: %s", entry.unique_id)
            _LOGGER.info("    Disabled by: %s", entry.disabled_by)
            _LOGGER.info("    Data: %s", entry.data)
            
            # Identify problematic states
            if entry.state in ["failed_unload", "setup_error", "setup_retry"]:
                _LOGGER.warning("    ⚠️  PROBLEMATIC: Entry is in error state!")
                problematic_entries.append(entry)
            elif not entry.data.get(CONF_BROKER):
                _LOGGER.warning("    ⚠️  PROBLEMATIC: Entry missing broker data!")
                problematic_entries.append(entry)
                
        if problematic_entries:
            _LOGGER.warning("%s: Found %d problematic entries that may need cleanup", context, len(problematic_entries))
            
        return problematic_entries

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - ask for host."""
        _LOGGER.info("VictronConfigFlow.async_step_user called with input: %s", user_input)
        _LOGGER.info("VictronConfigFlow user step - flow_id: %s, context: %s", self.flow_id, self.context)
        
        # Always show form first if no input provided
        if user_input is None:
            _LOGGER.info("VictronConfigFlow showing initial user form")
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors={}
            )
            
        # Process user input - for now, just create a basic entry to test
        _LOGGER.info("VictronConfigFlow processing user input: %s", user_input)
        
        # Check for existing entries with same broker
        broker = user_input[CONF_BROKER]
        existing_entries = [
            entry for entry in self._async_current_entries()
            if entry.data.get(CONF_BROKER) == broker
        ]
        if existing_entries:
            entry = existing_entries[0]
            _LOGGER.info("VictronConfigFlow: Found existing entry for broker %s", broker)
            _LOGGER.info("  Entry ID: %s", entry.entry_id)
            _LOGGER.info("  Entry title: %s", entry.title)
            _LOGGER.info("  Entry state: %s", entry.state)
            _LOGGER.info("  Entry data: %s", entry.data)
            _LOGGER.info("  Entry unique_id: %s", entry.unique_id)
            _LOGGER.info("  Entry disabled_by: %s", entry.disabled_by)
            return self.async_abort(reason="already_configured")
        
        # Log all existing entries for diagnostics
        problematic_entries = self._log_existing_entries("USER_FLOW")
        
        try:
            info = await validate_input(self.hass, user_input)
            _LOGGER.info("VictronConfigFlow validation successful: %s", info)
            
            # For now, just create a simple entry to test the flow
            _LOGGER.info("VictronConfigFlow creating config entry for broker: %s", broker)
            return self.async_create_entry(
                title=f"Victron Energy ({broker})",
                data={
                    CONF_BROKER: broker,
                    CONF_PORT: 1883,
                }
            )
            
        except CannotConnect:
            _LOGGER.warning("VictronConfigFlow: Cannot connect error")
            errors = {"base": "cannot_connect"}
        except InvalidHost:
            _LOGGER.warning("VictronConfigFlow: Invalid host error")
            errors = {"base": "invalid_host"}
        except Exception as ex:
            _LOGGER.exception("VictronConfigFlow: Unexpected exception: %s", ex)
            errors = {"base": "unknown"}

        _LOGGER.info("VictronConfigFlow showing user form with errors: %s", errors)
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle password step for token authentication."""
        errors: dict[str, str] = {}
        broker = self.context.get("broker")
        
        if user_input is not None:
            try:
                info = await validate_secure_mqtt_connection(
                    self.hass, broker, user_input[CONF_PASSWORD]
                )
                
                # Create entry with secure MQTT config
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_BROKER: broker,
                        CONF_PORT: 8883,
                        CONF_USERNAME: f"token/homeassistant/{info['ha_device_id']}",
                        CONF_TOKEN: info["token"],
                        "ha_device_id": info["ha_device_id"],
                    }
                )
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="password", 
            data_schema=STEP_PASSWORD_DATA_SCHEMA, 
            errors=errors,
            description_placeholders={"host": broker if broker else "unknown"}
        )

    async def async_step_ssdp_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle password step for SSDP discovered device."""
        errors: dict[str, str] = {}
        broker = self.context.get("broker")
        friendly_name = self.context.get("title_placeholders", {}).get("name", "Victron Energy")
        
        if user_input is not None:
            try:
                info = await validate_secure_mqtt_connection(
                    self.hass, broker, user_input[CONF_PASSWORD]
                )
                
                # Create entry with secure MQTT config
                return self.async_create_entry(
                    title=friendly_name,
                    data={
                        CONF_BROKER: broker,
                        CONF_PORT: 8883,
                        CONF_USERNAME: f"token/homeassistant/{info['ha_device_id']}",
                        CONF_TOKEN: info["token"],
                        "ha_device_id": info["ha_device_id"],
                    }
                )
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            
            # If there are errors, show menu instead of password form again
            if errors:
                return await self.async_step_ssdp_password_menu()

        return self.async_show_form(
            step_id="ssdp_password", 
            data_schema=STEP_PASSWORD_DATA_SCHEMA, 
            errors=errors,
            description_placeholders=self.context.get("title_placeholders", {})
        )

    async def async_step_ssdp_password_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle menu after password authentication fails."""
        if user_input is not None:
            if user_input["next_step"] == "retry":
                # Go back to confirmation step
                return await self.async_step_ssdp_confirm()
            else:
                # Cancel the flow but allow re-discovery by not marking unique_id as handled
                # We reset the unique_id to None first, so it won't be marked as permanently handled
                original_unique_id = self.unique_id
                await self.async_set_unique_id(None, raise_on_progress=False)
                _LOGGER.info("Config flow cancelled by user for device %s, allowing re-discovery", original_unique_id)
                return self.async_abort(reason="user_cancelled")

        return self.async_show_form(
            step_id="ssdp_password_menu",
            data_schema=STEP_SSDP_PASSWORD_MENU_SCHEMA,
            description_placeholders=self.context.get("title_placeholders", {})
        )

    async def async_step_ssdp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation for SSDP discovered device."""
        _LOGGER.info("ssdp_confirm called with input: %s", user_input)
        _LOGGER.info("context title_placeholders: %s", self.context.get("title_placeholders"))
        
        broker = self.context.get("broker")
        friendly_name = self.context.get("title_placeholders", {}).get("name", "Victron Energy")
        
        if user_input is not None:
            # Now test basic MQTT connection after user confirmation
            if await _test_basic_mqtt_connection(self.hass, broker):
                # Basic MQTT works, create entry with simple config
                return self.async_create_entry(
                    title=friendly_name,
                    data={
                        CONF_BROKER: broker,
                        CONF_PORT: 1883,
                    }
                )
            else:
                # Basic MQTT failed, ask for password for token auth
                return await self.async_step_ssdp_password()

        _LOGGER.info("About to show ssdp_confirm form")
        result = self.async_show_form(
            step_id="ssdp_confirm",
            data_schema=STEP_SSDP_CONFIRM_SCHEMA,
            description_placeholders=self.context.get("title_placeholders", {})
        )
        _LOGGER.info("Form result created: %s", result)
        return result

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP discovery."""

        # Debug
        _LOGGER.info("Discovered SSDP info: %s", discovery_info)

        host = discovery_info.ssdp_headers.get("_host")
        friendly_name = discovery_info.upnp.get("friendlyName", "Victron Energy GX")
        unique_id = discovery_info.upnp.get("X_VrmPortalId")
        if unique_id is None:
            return self.async_abort(reason="missing_unique_id")
        home_assistant_discovery = discovery_info.upnp.get("X_HomeAssistantDiscovery")
        if home_assistant_discovery is None:
            return self.async_abort(reason="no_discovery_support")

        await self.async_set_unique_id(unique_id)
        _LOGGER.info("Setting unique_id: %s", unique_id)
        
        # Check existing entries before unique ID check
        problematic_entries = self._log_existing_entries("SSDP_FLOW")
                
        # Check if this unique ID is already configured
        _LOGGER.info("Checking if unique_id %s is already configured", unique_id)
        try:
            self._abort_if_unique_id_configured(
                updates={
                    CONF_BROKER: host,
                }
            )
            _LOGGER.info("Unique_id %s is not configured, proceeding with flow", unique_id)
        except Exception as ex:
            _LOGGER.info("Unique_id %s already configured, aborting flow: %s", unique_id, ex)
            # Check if the existing entry is accessible
            existing_entry = self.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, unique_id)
            if existing_entry:
                _LOGGER.info("Existing entry details: %s", {
                    'entry_id': existing_entry.entry_id,
                    'title': existing_entry.title,
                    'state': existing_entry.state,
                    'data': existing_entry.data,
                    'disabled_by': existing_entry.disabled_by
                })
            raise

        self.context["title_placeholders"] = {
            "name": friendly_name or "Victron Energy Device",
            "host": str(host) if host else "unknown",
        }
        self.context["broker"] = host
        
        _LOGGER.info("SSDP confirmation - friendly_name: %s, host: %s", friendly_name, host)
        
        # Show confirmation step first, before testing connection
        result = self.async_show_form(
            step_id="ssdp_confirm",
            data_schema=STEP_SSDP_CONFIRM_SCHEMA,
            description_placeholders=self.context["title_placeholders"]
        )
        _LOGGER.info("Form result created: %s", result)
        return result


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
