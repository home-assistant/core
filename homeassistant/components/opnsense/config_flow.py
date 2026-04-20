"""Config flow for OPNsense."""

import logging
from typing import Any

from aiopnsense import (
    OPNsenseBelowMinFirmware,
    OPNsenseClient,
    OPNsenseConnectionError,
    OPNsenseInvalidAuth,
    OPNsenseInvalidURL,
    OPNsensePrivilegeMissing,
    OPNsenseSSLError,
    OPNsenseTimeoutError,
    OPNsenseUnknownFirmware,
)
from requests.exceptions import ConnectionError as requestsConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_API_SECRET): str,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)


class OPNsenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """OPNsense config flow."""

    def __init__(self) -> None:
        """Initialize OPNsense config flow."""
        self.available_interfaces: list[str] | None = None

    async def _show_setup_form(
        self,
        user_input: dict[Any, Any] | None = None,
        errors: dict[Any, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        description_placeholders = {
            "doc_url": "https://www.home-assistant.io/integrations/opnsense/"
        }

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors or {},
            description_placeholders=description_placeholders,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user step."""

        errors = {}

        if user_input is None:
            return await self._show_setup_form(user_input, None)

        self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

        verify_ssl = user_input[CONF_VERIFY_SSL]
        session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)
        client = OPNsenseClient(
            user_input[CONF_URL],
            user_input[CONF_API_KEY],
            user_input[CONF_API_SECRET],
            session,
            opts={"verify_ssl": verify_ssl},
        )

        try:
            await self._async_check_connection(client)
        except OPNsenseInvalidAuth:
            errors["base"] = "invalid_auth"
        except OPNsensePrivilegeMissing:
            errors["base"] = "previlege_missing"
        except OPNsenseInvalidURL:
            errors["base"] = "invalid_url"
        except OPNsenseSSLError:
            errors["base"] = "ssl_error"
        except OPNsenseConnectionError, OPNsenseTimeoutError, requestsConnectionError:
            errors["base"] = "cannot_connect"
        except OPNsenseUnknownFirmware:
            errors["base"] = "invalid_version"
        except OPNsenseBelowMinFirmware:
            errors["base"] = "invalid_version"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=user_input[CONF_URL], data=user_input)

        return await self._show_setup_form(user_input, errors)

    async def async_step_import(
        self, import_data: (dict[str, Any])
    ) -> ConfigFlowResult:
        """Import a Yaml config."""
        self._async_abort_entries_match({CONF_URL: import_data[CONF_URL]})

        # Test connection
        session = async_get_clientsession(
            self.hass, verify_ssl=import_data[CONF_VERIFY_SSL]
        )
        client = OPNsenseClient(
            import_data[CONF_URL],
            import_data[CONF_API_KEY],
            import_data[CONF_API_SECRET],
            session,
            opts={"verify_ssl": import_data[CONF_VERIFY_SSL]},
        )
        try:
            await client.validate()
        except OPNsenseInvalidURL:
            return self.async_abort(reason="invalid_url")
        except OPNsenseInvalidAuth:
            return self.async_abort(reason="invalid_auth")
        except OPNsensePrivilegeMissing:
            return self.async_abort(reason="previlege_missing")
        except OPNsenseSSLError:
            return self.async_abort(reason="ssl_error")
        except OPNsenseConnectionError, OPNsenseTimeoutError, requestsConnectionError:
            return self.async_abort(reason="cannot_connect")
        except OPNsenseUnknownFirmware:
            return self.async_abort(reason="invalid_version")
        except OPNsenseBelowMinFirmware:
            return self.async_abort(reason="invalid_version")
        except Exception:  # Allowed in config flows
            _LOGGER.exception("Unexpected exception during import")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(title=import_data[CONF_URL], data=import_data)

    async def _async_check_connection(self, client: OPNsenseClient) -> None:
        """Check connection to OPNsense."""
        await client.validate()
