"""Config flow for Unraid integration."""

from __future__ import annotations

import logging
from typing import Any

from awesomeversion import AwesomeVersion, AwesomeVersionException
from unraid_api import UnraidClient
from unraid_api.exceptions import (
    UnraidAuthenticationError,
    UnraidConnectionError,
    UnraidSSLError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_API_VERSION = "4.21.0"


class UnraidFlowError(Exception):
    """Base exception for Unraid config flow errors."""

    def __init__(self, error_key: str | None = None) -> None:
        """Initialize the error."""
        self.error_key = error_key
        super().__init__()


class UnraidAbortFlow(Exception):
    """Exception to abort the config flow."""

    def __init__(self, reason: str) -> None:
        """Initialize the abort exception."""
        self.reason = reason
        super().__init__()


USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_API_KEY): str,
    }
)


class UnraidConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Unraid."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._server_uuid: str | None = None
        self._server_hostname: str | None = None
        self._use_ssl: bool = True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._validate_and_create_entry(user_input)
            except UnraidAbortFlow as err:
                return self.async_abort(reason=err.reason)
            except UnraidFlowError as err:
                if err.error_key == CONF_API_KEY:
                    errors[CONF_API_KEY] = "invalid_auth"
                elif err.error_key:
                    errors["base"] = err.error_key
            else:
                # Successfully validated - create entry
                await self.async_set_unique_id(self._server_uuid)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._server_hostname or user_input[CONF_HOST],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input.get(CONF_PORT, DEFAULT_PORT),
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_SSL: self._use_ssl,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def _validate_and_create_entry(self, user_input: dict[str, Any]) -> None:
        """Validate connection and prepare entry data.

        Raises UnraidAbortFlow or UnraidFlowError on validation issues.
        """
        host = user_input[CONF_HOST].strip()
        api_key = user_input[CONF_API_KEY].strip()
        port = user_input.get(CONF_PORT, DEFAULT_PORT)

        # Try HTTPS first
        try:
            await self._test_connection_with_ssl(host, api_key, port, use_ssl=True)
        except UnraidAbortFlow:
            raise
        except UnraidFlowError:
            # SSL failed, try HTTP
            _LOGGER.debug("HTTPS connection failed, trying HTTP")
            await self._test_connection_with_ssl(host, api_key, port, use_ssl=False)

    async def _test_connection_with_ssl(
        self, host: str, api_key: str, port: int, use_ssl: bool
    ) -> None:
        """Test connection with specified SSL setting.

        Raises UnraidAbortFlow or UnraidFlowError on validation issues.
        """
        api_client = UnraidClient(
            host=host,
            api_key=api_key,
            https_port=port,
            http_port=port,
            verify_ssl=use_ssl,
            session=async_get_clientsession(self.hass, verify_ssl=use_ssl),
        )

        try:
            await self._validate_connection(api_client)
        except UnraidSSLError as err:
            if use_ssl:
                # Try HTTP fallback
                raise UnraidFlowError from err
            # HTTP also failed with SSL error
            raise UnraidFlowError("base") from err
        except UnraidAuthenticationError as err:
            raise UnraidFlowError(CONF_API_KEY) from err
        except UnraidConnectionError as err:
            raise UnraidFlowError("cannot_connect") from err
        except UnraidAbortFlow:
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected error during connection test")
            raise UnraidFlowError("unknown") from err
        finally:
            await api_client.close()

        # Success - set SSL preference
        self._use_ssl = use_ssl

    async def _validate_connection(self, api_client: UnraidClient) -> None:
        """Validate connection, version, and fetch server info.

        Raises UnraidAbortFlow or connection exceptions.
        """
        await api_client.test_connection()

        try:
            version_info = await api_client.get_version()
        except Exception as err:
            _LOGGER.exception("Failed to get version info")
            raise UnraidAbortFlow(reason="cannot_get_version") from err

        api_version = version_info.get("api", "0.0.0")
        if not self._is_supported_version(api_version):
            raise UnraidAbortFlow(reason="unsupported_version")

        try:
            server_info = await api_client.get_server_info()
        except Exception as err:
            _LOGGER.exception("Failed to get server info")
            raise UnraidFlowError("base") from err

        if not server_info.uuid:
            raise UnraidAbortFlow(reason="no_server_uuid")

        self._server_uuid = server_info.uuid
        self._server_hostname = server_info.hostname

    def _is_supported_version(self, api_version: str) -> bool:
        """Check if API version is supported using proper version parsing."""
        try:
            current = AwesomeVersion(api_version)
            minimum = AwesomeVersion(MIN_API_VERSION)
        except AwesomeVersionException:
            _LOGGER.error("Failed to parse API version: %s", api_version)
            return False
        return current >= minimum
