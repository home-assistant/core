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
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_VERIFY_SSL

from .const import (
    CONF_HTTP_PORT,
    CONF_HTTPS_PORT,
    DEFAULT_HTTP_PORT,
    DEFAULT_HTTPS_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MIN_API_VERSION = "4.21.0"


class UnraidConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Unraid."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._server_uuid: str | None = None
        self._server_hostname: str | None = None
        self._verify_ssl: bool = True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}
        abort_reason: str | None = None

        if user_input is not None:
            abort_reason = await self._test_connection(user_input, errors)

            if abort_reason:
                return self.async_abort(reason=abort_reason)

            if not errors:
                if not self._server_uuid:
                    return self.async_abort(reason="no_server_uuid")

                await self.async_set_unique_id(self._server_uuid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._server_hostname or user_input[CONF_HOST],
                    data={
                        **user_input,
                        CONF_VERIFY_SSL: self._verify_ssl,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_HTTP_PORT, default=DEFAULT_HTTP_PORT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                    vol.Optional(CONF_HTTPS_PORT, default=DEFAULT_HTTPS_PORT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def _test_connection(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> str | None:
        """Test connection to Unraid server and validate version.

        Returns abort reason if flow should be aborted, otherwise None.
        Populates errors dict with any validation errors.
        """
        host = user_input[CONF_HOST].strip()
        api_key = user_input[CONF_API_KEY].strip()
        http_port = user_input.get(CONF_HTTP_PORT, DEFAULT_HTTP_PORT)
        https_port = user_input.get(CONF_HTTPS_PORT, DEFAULT_HTTPS_PORT)

        self._verify_ssl = True

        api_client = UnraidClient(
            host=host,
            api_key=api_key,
            http_port=http_port,
            https_port=https_port,
            verify_ssl=True,
        )

        try:
            return await self._validate_connection(api_client, errors)
        except UnraidSSLError:
            # SSL failed, try without SSL verification
            await api_client.close()
            api_client = UnraidClient(
                host=host,
                api_key=api_key,
                http_port=http_port,
                https_port=https_port,
                verify_ssl=False,
            )
            try:
                result = await self._validate_connection(api_client, errors)
                if not errors:
                    self._verify_ssl = False
                return result
            finally:
                await api_client.close()
        finally:
            await api_client.close()

    async def _validate_connection(
        self, api_client: UnraidClient, errors: dict[str, str]
    ) -> str | None:
        """Validate connection, version, and fetch server info.

        Returns abort reason if flow should be aborted, otherwise None.
        Populates errors dict with any validation errors.
        Raises UnraidSSLError to trigger SSL fallback.
        """
        try:
            await api_client.test_connection()
        except UnraidAuthenticationError:
            errors[CONF_API_KEY] = "invalid_auth"
            return None
        except UnraidSSLError:
            raise
        except UnraidConnectionError:
            errors[CONF_HOST] = "cannot_connect"
            errors[CONF_HTTPS_PORT] = "check_port"
            return None
        except Exception:
            _LOGGER.exception("Unexpected error during connection test")
            errors["base"] = "unknown"
            return None

        try:
            version_info = await api_client.get_version()
        except Exception:
            _LOGGER.exception("Failed to get version info")
            errors["base"] = "unknown"
            return None

        api_version = version_info.get("api", "0.0.0")
        if not self._is_supported_version(api_version):
            return "unsupported_version"

        try:
            server_info = await api_client.get_server_info()
        except Exception:
            _LOGGER.exception("Failed to get server info")
            errors["base"] = "unknown"
            return None

        self._server_uuid = server_info.uuid
        self._server_hostname = server_info.hostname
        return None

    def _is_supported_version(self, api_version: str) -> bool:
        """Check if API version is supported using proper version parsing."""
        try:
            current = AwesomeVersion(api_version)
            minimum = AwesomeVersion(MIN_API_VERSION)
        except AwesomeVersionException:
            return True
        return current >= minimum
