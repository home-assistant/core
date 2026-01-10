"""Config flow for Unraid integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import aiohttp
from packaging.version import InvalidVersion, Version
from unraid_api import UnraidClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_STORAGE_INTERVAL,
    CONF_SYSTEM_INTERVAL,
    CONF_UPS_CAPACITY_VA,
    CONF_UPS_NOMINAL_POWER,
    DEFAULT_STORAGE_POLL_INTERVAL,
    DEFAULT_SYSTEM_POLL_INTERVAL,
    DEFAULT_UPS_CAPACITY_VA,
    DEFAULT_UPS_NOMINAL_POWER,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult

    from .coordinator import UnraidConfigEntry

_LOGGER = logging.getLogger(__name__)

MIN_API_VERSION = "4.21.0"
MIN_UNRAID_VERSION = "7.2.0"
MAX_HOSTNAME_LEN = 253
DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443
MIN_PORT = 1
MAX_PORT = 65535

# Custom config keys for ports (not in homeassistant.const)
CONF_HTTP_PORT = "http_port"
CONF_HTTPS_PORT = "https_port"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Unraid."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._server_uuid: str | None = None
        self._server_hostname: str | None = None
        self._verify_ssl: bool = True  # Track SSL verification setting

    @staticmethod
    def async_get_options_flow(
        config_entry: UnraidConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return UnraidOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate inputs
            validation_errors = self._validate_inputs(user_input)
            if validation_errors:
                errors.update(validation_errors)
            else:
                # Try to connect to server
                try:
                    _LOGGER.debug(
                        "Testing connection to Unraid server: %s", user_input[CONF_HOST]
                    )
                    await self._test_connection(user_input)
                    _LOGGER.info(
                        "Successfully connected to Unraid server: %s",
                        user_input[CONF_HOST],
                    )
                except InvalidAuthError:
                    errors[CONF_API_KEY] = "invalid_auth"
                    _LOGGER.warning(
                        "Invalid authentication for %s", user_input[CONF_HOST]
                    )
                except CannotConnectError:
                    # Show error on host and port fields for connection issues
                    errors[CONF_HOST] = "cannot_connect"
                    errors[CONF_HTTPS_PORT] = "check_port"
                    _LOGGER.warning("Cannot connect to %s", user_input[CONF_HOST])
                except UnsupportedVersionError:
                    errors["base"] = "unsupported_version"
                    _LOGGER.warning("Unsupported version for %s", user_input[CONF_HOST])
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception(
                        "Unexpected error connecting to %s", user_input[CONF_HOST]
                    )
                    errors["base"] = "unknown"

            # If no errors, create entry
            if not errors:
                # Use server UUID as unique ID (stable across hostname changes)
                # Fall back to host if UUID not available
                unique_id = self._server_uuid or user_input[CONF_HOST]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Use server hostname as title (more readable than IP)
                title = self._server_hostname or user_input[CONF_HOST]

                # Include SSL verification setting in config entry data
                entry_data = {
                    **user_input,
                    CONF_VERIFY_SSL: self._verify_ssl,
                }

                _LOGGER.info(
                    "Creating config entry for %s (UUID: %s) ports=%s/%s verify_ssl=%s",
                    title,
                    unique_id,
                    user_input.get(CONF_HTTP_PORT, DEFAULT_HTTP_PORT),
                    user_input.get(CONF_HTTPS_PORT, DEFAULT_HTTPS_PORT),
                    self._verify_ssl,
                )
                return self.async_create_entry(
                    title=title,
                    data=entry_data,
                    options={
                        CONF_SYSTEM_INTERVAL: DEFAULT_SYSTEM_POLL_INTERVAL,
                        CONF_STORAGE_INTERVAL: DEFAULT_STORAGE_POLL_INTERVAL,
                        CONF_UPS_CAPACITY_VA: DEFAULT_UPS_CAPACITY_VA,
                        CONF_UPS_NOMINAL_POWER: DEFAULT_UPS_NOMINAL_POWER,
                    },
                )

        # Show form with optional HTTP and HTTPS port fields
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_HTTP_PORT, default=DEFAULT_HTTP_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_PORT, max=MAX_PORT)
                ),
                vol.Optional(CONF_HTTPS_PORT, default=DEFAULT_HTTPS_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_PORT, max=MAX_PORT)
                ),
                vol.Required(CONF_API_KEY): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "min_version": MIN_UNRAID_VERSION,
            },
        )

    def _validate_inputs(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate user inputs."""
        errors = {}

        # Host validation
        host = user_input.get(CONF_HOST, "").strip()
        if not host:
            errors[CONF_HOST] = "required"
        elif len(host) > MAX_HOSTNAME_LEN:
            errors[CONF_HOST] = "invalid_hostname"

        # API key validation
        api_key = user_input.get(CONF_API_KEY, "").strip()
        if not api_key:
            errors[CONF_API_KEY] = "required"

        return errors

    async def _test_connection(self, user_input: dict[str, Any]) -> None:
        """Test connection to Unraid server and validate version."""
        host = user_input[CONF_HOST].strip()
        api_key = user_input[CONF_API_KEY].strip()
        http_port = user_input.get(CONF_HTTP_PORT, DEFAULT_HTTP_PORT)
        https_port = user_input.get(CONF_HTTPS_PORT, DEFAULT_HTTPS_PORT)

        # Reset verify_ssl to default
        self._verify_ssl = True

        # First attempt: try with SSL verification enabled
        # This works for: HTTP-only mode (No SSL) and Strict mode (myunraid.net)
        api_client = UnraidClient(
            host=host,
            api_key=api_key,
            http_port=http_port,
            https_port=https_port,
            verify_ssl=True,
        )

        try:
            await self._validate_connection(api_client, host)
        except CannotConnectError as err:
            # Check if this might be a self-signed certificate error
            error_str = str(err).lower()
            if "ssl" in error_str or "certificate" in error_str:
                # Retry with SSL verification disabled (for self-signed certs)
                _LOGGER.debug(
                    "SSL verification failed, retrying with verify_ssl=False: %s", err
                )
                await api_client.close()
                api_client = UnraidClient(
                    host=host,
                    api_key=api_key,
                    http_port=http_port,
                    https_port=https_port,
                    verify_ssl=False,
                )
                try:
                    await self._validate_connection(api_client, host)
                    # Success with SSL verification disabled - remember this
                    self._verify_ssl = False
                    _LOGGER.info(
                        "Connected to %s with self-signed cert (SSL verify disabled)",
                        host,
                    )
                finally:
                    await api_client.close()
            else:
                raise
        finally:
            await api_client.close()

    async def _validate_connection(self, api_client: UnraidClient, host: str) -> None:
        """Validate connection, version, and fetch server info."""
        try:
            # Test connection
            await api_client.test_connection()

            # Get version and server info
            version_info = await api_client.get_version()

            # Check version - api.py returns "api" not "api_version"
            api_version = version_info.get("api", "0.0.0")
            unraid_version = version_info.get("unraid", "0.0.0")

            if not self._is_supported_version(api_version):
                msg = (
                    f"Unraid {unraid_version} (API {api_version}) not supported. "
                    f"Minimum required: Unraid {MIN_UNRAID_VERSION} "
                    f"(API {MIN_API_VERSION})"
                )
                raise UnsupportedVersionError(msg)  # noqa: TRY301

            # Get server UUID and hostname for unique identification
            await self._fetch_server_info(api_client, host)

        except (InvalidAuthError, CannotConnectError, UnsupportedVersionError):
            raise
        except aiohttp.ClientResponseError as err:
            self._handle_http_error(err, host)
        except aiohttp.ClientConnectorError as err:
            msg = f"Cannot connect to {host} - {err}"
            raise CannotConnectError(msg) from err
        except aiohttp.ClientError as err:
            msg = f"Connection error: {err}"
            raise CannotConnectError(msg) from err
        except Exception as err:  # noqa: BLE001
            self._handle_generic_error(err)

    async def _fetch_server_info(self, api_client: UnraidClient, host: str) -> None:
        """Fetch server UUID and hostname for unique identification."""
        info_query = """
            query {
                info {
                    system { uuid }
                    os { hostname }
                }
            }
        """
        info_data = await api_client.query(info_query)
        info = info_data.get("info", {})
        system = info.get("system", {})
        os_info = info.get("os", {})

        self._server_uuid = system.get("uuid")
        self._server_hostname = os_info.get("hostname") or host

    def _handle_http_error(self, err: aiohttp.ClientResponseError, host: str) -> None:
        """Handle HTTP errors from API client."""
        if err.status in (401, 403):
            msg = "Invalid API key or insufficient permissions"
            raise InvalidAuthError(msg) from err
        msg = f"HTTP error {err.status}: {err.message}"
        raise CannotConnectError(msg) from err

    def _handle_generic_error(self, err: Exception) -> None:
        """Handle generic errors, mapping to appropriate exception types."""
        error_str = str(err).lower()
        if "401" in error_str or "unauthorized" in error_str:
            msg = "Invalid API key or insufficient permissions"
            raise InvalidAuthError(msg) from err
        if "ssl" in error_str or "certificate" in error_str:
            msg = f"SSL error: {err}. Try disabling SSL verification."
            raise CannotConnectError(msg) from err
        _LOGGER.exception("Unexpected error during connection test")
        raise CannotConnectError(f"Unexpected error: {err}") from err

    def _is_supported_version(self, api_version: str) -> bool:
        """Check if API version is supported using proper version parsing."""
        try:
            # Parse versions properly handling suffixes like "-beta", "a", etc.
            current = Version(api_version)
            minimum = Version(MIN_API_VERSION)
        except InvalidVersion:
            # Fallback to basic comparison if packaging fails
            _LOGGER.warning(
                "Could not parse API version '%s', assuming supported", api_version
            )
            return True
        return current >= minimum

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id", "")
        )

        if reconfigure_entry is None:
            return self.async_abort(reason="reconfigure_failed")

        if user_input is not None:
            # Validate inputs
            validation_errors = self._validate_inputs(user_input)
            if validation_errors:
                errors.update(validation_errors)
            else:
                try:
                    await self._test_connection(user_input)

                    # Update the config entry with new data
                    self.hass.config_entries.async_update_entry(
                        reconfigure_entry,
                        data=user_input,
                    )

                    await self.hass.config_entries.async_reload(
                        reconfigure_entry.entry_id
                    )
                    return self.async_abort(reason="reconfigure_successful")

                except InvalidAuthError:
                    errors["base"] = "invalid_auth"
                except CannotConnectError:
                    errors["base"] = "cannot_connect"
                except UnsupportedVersionError:
                    errors["base"] = "unsupported_version"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected error during reconfigure")
                    errors["base"] = "unknown"

        # Pre-fill form with existing values
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=reconfigure_entry.data.get(CONF_HOST, "")
                    ): str,
                    vol.Optional(
                        CONF_HTTP_PORT,
                        default=reconfigure_entry.data.get(
                            CONF_HTTP_PORT, DEFAULT_HTTP_PORT
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_PORT, max=MAX_PORT)),
                    vol.Optional(
                        CONF_HTTPS_PORT,
                        default=reconfigure_entry.data.get(
                            CONF_HTTPS_PORT, DEFAULT_HTTPS_PORT
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_PORT, max=MAX_PORT)),
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )


class UnraidOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Unraid options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the init step to configure polling intervals and UPS settings."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options

        # Check if UPS devices are detected
        has_ups = False
        if (
            hasattr(self.config_entry, "runtime_data")
            and self.config_entry.runtime_data
        ):
            system_coordinator = self.config_entry.runtime_data.system_coordinator
            if system_coordinator.data and system_coordinator.data.ups_devices:
                has_ups = True

        # Build schema - base options always shown
        schema_dict: dict[vol.Marker, Any] = {
            vol.Optional(
                CONF_SYSTEM_INTERVAL,
                default=options.get(CONF_SYSTEM_INTERVAL, DEFAULT_SYSTEM_POLL_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            vol.Optional(
                CONF_STORAGE_INTERVAL,
                default=options.get(
                    CONF_STORAGE_INTERVAL, DEFAULT_STORAGE_POLL_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
        }

        # Add UPS options only if UPS is detected
        if has_ups:
            schema_dict[
                vol.Optional(
                    CONF_UPS_CAPACITY_VA,
                    default=options.get(CONF_UPS_CAPACITY_VA, DEFAULT_UPS_CAPACITY_VA),
                )
            ] = vol.All(vol.Coerce(int), vol.Range(min=0, max=100000))
            schema_dict[
                vol.Optional(
                    CONF_UPS_NOMINAL_POWER,
                    default=options.get(
                        CONF_UPS_NOMINAL_POWER, DEFAULT_UPS_NOMINAL_POWER
                    ),
                )
            ] = vol.All(vol.Coerce(int), vol.Range(min=0, max=100000))

        data_schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )


class InvalidAuthError(HomeAssistantError):
    """Exception for invalid authentication."""


class CannotConnectError(HomeAssistantError):
    """Exception for cannot connect to server."""


class UnsupportedVersionError(HomeAssistantError):
    """Exception for unsupported version."""
